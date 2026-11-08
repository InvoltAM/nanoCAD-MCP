using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

namespace CadEngine.Services
{
    /// <summary>
    /// Доступ к CAE-модели nanoCAD BIM Электро: DI-контейнер (Nanosoft.Platform),
    /// сеть модели (IAcadNet) и её узлы (щиты, фидеры, потребители),
    /// каталог БД оборудования и создание групп.
    /// Работает полностью через рефлексию — без compile-time ссылок на сборки Электро;
    /// сигнатуры типов добыты рантайм-разведкой (ElectroInspectService).
    /// </summary>
    public class ElectroModelService
    {
        // Сигнатуры, найденные разведкой (см. docs/Реверс-анализ):
        private const string ContainerTypeName  = "Nanosoft.Platform.Platform.IContainer";
        private const string NetTypeName        = "Nanosoft.Acad.IAcadNet";
        private const string NetFactoryTypeName = "Nanosoft.Acad.Net.IAcadNetFactory";
        private const string BoardTypeName      = "Nanosoft.Electrica.ElBoard";

        private static object? _container;
        private static string? _containerSource;
        private static object? _net;
        private static string? _netSource;

        /// <summary>
        /// Сканирует статические свойства и поля всех Nanosoft-сборок процесса:
        /// ищет акцессоры контейнера DI, сети модели и фабрики сети.
        /// Чистая разведка — геттеры не вызываются.
        /// </summary>
        public object DiscoverAccessors()
        {
            try
            {
                var hits = new List<object>();
                foreach (var asm in NanosoftAssemblies())
                {
                    foreach (var t in SafeTypes(asm))
                    {
                        foreach (var hit in InterestingStaticMembers(t))
                            hits.Add(hit);
                    }
                }
                return new { success = true, count = hits.Count, accessors = hits };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        /// <summary>
        /// Резолвит компонент из DI-контейнера Электро по полному имени типа
        /// (обычно — интерфейса, напр. Nanosoft.Electrica.IDbElFiderCraetor).
        /// </summary>
        public object ResolveComponent(string typeName)
        {
            try
            {
                var t = FindType(typeName);
                if (t == null)
                    return new { success = false, error = $"Тип {typeName} не найден ни в одной загруженной сборке" };

                var container = GetContainer(out var err);
                if (container == null)
                    return new { success = false, error = err };

                object? instance;
                try
                {
                    instance = ResolveInternal(container, t);
                }
                catch (Exception ex)
                {
                    return new
                    {
                        success = false,
                        error = "DI Resolve: " + (ex.InnerException?.Message ?? ex.Message),
                        container = _containerSource
                    };
                }

                if (instance == null)
                    return new { success = false, error = "Resolve вернул null (тип не зарегистрирован в контейнере?)", container = _containerSource };

                return new
                {
                    success = true,
                    requested = t.FullName,
                    instance_type = instance.GetType().FullName,
                    instance_assembly = instance.GetType().Assembly.GetName().Name,
                    container = _containerSource,
                    interfaces = instance.GetType().GetInterfaces().Select(i => i.Name).ToList()
                };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        /// <summary>
        /// Информация о текущей сети модели: источник доступа, число узлов,
        /// распределение по типам, найденные щиты.
        /// </summary>
        public object GetNetInfo()
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var net = GetNet(out var err);
                    if (net == null)
                        return new { success = false, error = err };

                    var counts = new Dictionary<string, int>();
                    var boards = new List<object>();
                    int total = 0;

                    if (net.GetType().GetProperty("Nodes")?.GetValue(net) is IEnumerable nodes)
                    {
                        foreach (var node in nodes)
                        {
                            if (node == null) continue;
                            total++;
                            var tn = node.GetType().FullName ?? "?";
                            counts[tn] = counts.TryGetValue(tn, out var c) ? c + 1 : 1;
                            if (tn == BoardTypeName && boards.Count < 50)
                                boards.Add(DescribeNode(node));
                            if (total > 20000) break;
                        }
                    }

                    return new
                    {
                        success = true,
                        net_source = _netSource,
                        container = _containerSource,
                        nodes_total = total,
                        type_counts = counts.OrderByDescending(kv => kv.Value).Take(40)
                            .ToDictionary(kv => kv.Key, kv => kv.Value),
                        boards
                    };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message, inner = ex.InnerException?.Message };
                }
            });
        }

        /// <summary>Список щитов (ElBoard) в текущей модели с наполнением.</summary>
        public object ListBoards()
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var net = GetNet(out var err);
                    if (net == null)
                        return new { success = false, error = err };

                    var boards = new List<object>();
                    if (net.GetType().GetProperty("Nodes")?.GetValue(net) is IEnumerable nodes)
                    {
                        foreach (var node in nodes)
                        {
                            if (node == null || node.GetType().FullName != BoardTypeName) continue;
                            boards.Add(new
                            {
                                title = GetProp<string>(node, "TitleName"),
                                ac_id = GetProp<object>(node, "AcId")?.ToString(),
                                db_type = GetProp<object>(node, "Db")?.GetType().Name,
                                input_fiders = CollectionCount(GetProp<object>(node, "InputFiders")),
                                out_fiders = CollectionCount(GetProp<object>(node, "OutFiders")),
                                shell_filling = CollectionCount(GetProp<object>(node, "ShellFilling"))
                            });
                        }
                    }
                    return new { success = true, net_source = _netSource, count = boards.Count, boards };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message, inner = ex.InnerException?.Message };
                }
            });
        }

        /// <summary>Узлы модели по фильтру имени типа (подстрока; "all" — все).</summary>
        public object ListNodes(string typeFilter)
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var net = GetNet(out var err);
                    if (net == null) return new { success = false, error = err };

                    var list = new List<object>();
                    if (net.GetType().GetProperty("Nodes")?.GetValue(net) is IEnumerable nodes)
                    {
                        foreach (var node in nodes)
                        {
                            if (node == null) continue;
                            var tn = node.GetType().FullName ?? "?";
                            if (!string.IsNullOrEmpty(typeFilter) && typeFilter != "all"
                                && !tn.Contains(typeFilter, StringComparison.OrdinalIgnoreCase)) continue;
                            list.Add(DescribeNode(node));
                            if (list.Count >= 500) break;
                        }
                    }
                    return new { success = true, count = list.Count, nodes = list };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message };
                }
            });
        }

        /// <summary>
        /// Полный дамп значений свойств узла модели по AcId
        /// (enum — с числовым значением, вложенные Db-объекты — рекурсивно).
        /// </summary>
        public object DumpNode(string acId)
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var net = GetNet(out var err);
                    if (net == null) return new { success = false, error = err };

                    var target = FindNodeByAcId(net, acId);
                    if (target == null)
                        return new { success = false, error = $"Узел с AcId {acId} не найден" };

                    return DumpNodeDeep(target, 0);
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message, inner = ex.InnerException?.Message };
                }
            });
        }

        /// <summary>
        /// PoC M2: создать тестовую группу (фидер) в существующем щите.
        /// DbElFiderKitItem конструируется программно: enum'ы и Db-автомат
        /// копируются с эталонного отходящего фидера этого же щита.
        /// </summary>
        public object CreateTestGroup(string boardAcId)
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var net = GetNet(out var err);
                    if (net == null) return new { success = false, error = err };

                    var board = FindNodeByAcId(net, boardAcId);
                    if (board == null)
                        return new { success = false, error = $"Щит {boardAcId} не найден в модели" };
                    if (board.GetType().FullName != BoardTypeName)
                        return new { success = false, error = $"Узел {boardAcId} не ElBoard, а {board.GetType().FullName}" };

                    // Эталонный отходящий фидер щита
                    object? refFider = null;
                    if (GetProp<object>(board, "OutFiders") is IEnumerable outs)
                        foreach (var f in outs) { refFider = f; break; }
                    if (refFider == null)
                        return new { success = false, error = "У щита нет отходящих фидеров — не с чего копировать параметры" };

                    // Конструируем DbElFiderKitItem
                    var kitType = FindType("Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElFiderKitItem");
                    if (kitType == null)
                        return new { success = false, error = "Тип DbElFiderKitItem не найден" };
                    var kit = Activator.CreateInstance(kitType)!;

                    var copied = new List<string>();
                    foreach (var (dst, srcName) in new[]
                        { ("FiderType", "FiderType"), ("PoleCount", "PhaseCount"), ("FiderFilling", "FiderFilling") })
                    {
                        if (CopyEnumValue(kit, dst, refFider, srcName))
                            copied.Add($"{dst} <= {srcName}");
                    }
                    SetPropValue(kit, "Text", "MCP-TEST");

                    // Db-автомат эталонного фидера
                    var refAutomat = GetProp<object>(refFider, "SafeAutomat");
                    var refDbAutomat = refAutomat != null ? GetProp<object>(refAutomat, "Db") : null;
                    if (refDbAutomat != null)
                    {
                        SetPropValue(kit, "SafeAutomat", refDbAutomat);
                        copied.Add("SafeAutomat <= refFider.SafeAutomat.Db");
                    }

                    // Создание фидера через штатный компонент Электро
                    var container = GetContainer(out var cerr);
                    if (container == null) return new { success = false, error = cerr };
                    var craetorType = FindType("Nanosoft.Electrica.IDbElFiderCraetor");
                    var craetor = ResolveInternal(container, craetorType!);
                    if (craetor == null)
                        return new { success = false, error = "IDbElFiderCraetor не резолвится из контейнера" };

                    int before = CollectionCount(GetProp<object>(board, "OutFiders"));
                    object? newFider;
                    try
                    {
                        newFider = craetor.GetType().GetMethod("CreateNewFider")!
                            .Invoke(craetor, new[] { kit, board });
                    }
                    catch (Exception ex)
                    {
                        return new
                        {
                            success = false,
                            error = "CreateNewFider: " + (ex.InnerException?.Message ?? ex.Message),
                            copied
                        };
                    }
                    int after = CollectionCount(GetProp<object>(board, "OutFiders"));

                    // Сохранение в базу документа
                    var paperId = ExtractPaperId(boardAcId);
                    string saveMsg;
                    try
                    {
                        net.GetType().GetMethod("SaveObject")!.Invoke(net, new object?[] { board, true, paperId });
                        saveMsg = $"SaveObject(board, deepSave=true, paperId={paperId}) выполнен";
                    }
                    catch (Exception ex)
                    {
                        saveMsg = "SaveObject: " + (ex.InnerException?.Message ?? ex.Message);
                    }

                    return new
                    {
                        success = true,
                        copied,
                        out_fiders_before = before,
                        out_fiders_after = after,
                        create_returned = newFider?.GetType().FullName ?? "void/null",
                        save = saveMsg,
                        note = "Проверьте в nanoCAD панель «Сеть проекта»/щит РУ — должна появиться новая группа"
                    };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message, inner = ex.InnerException?.Message };
                }
            });
        }

        /// <summary>
        /// Каталог автоматических выключателей из активной БД оборудования.
        /// Фильтры: nominal (номинальный ток, А; 0 — все), poles (число полюсов; 0 — все).
        /// </summary>
        public object ListDbAutomats(double nominal, int poles)
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var (proxy, perr) = GetDbProxy();
                    if (proxy == null) return new { success = false, error = perr };

                    var automatType = FindType("Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElAutomat")!;
                    var items = LoadDbTable(proxy, automatType, out var lerr);
                    if (items == null) return new { success = false, error = lerr };

                    var list = new List<object>();
                    foreach (var it in items)
                    {
                        if (it == null) continue;
                        double nom = GetProp<double>(it, "NominalCur");
                        string poleStr = GetProp<object>(it, "DbPoleCount")?.ToString() ?? "";
                        if (nominal > 0 && Math.Abs(nom - nominal) > 0.01) continue;
                        if (poles > 0 && !poleStr.Contains($"_{poles}P") && !poleStr.Contains(poles.ToString())) continue;
                        list.Add(new
                        {
                            db_id = GetProp<int>(it, "DbId"),
                            name = GetProp<string>(it, "DbName"),
                            series = GetProp<string>(it, "DbSeries"),
                            nominal_cur = nom,
                            poles = poleStr,
                            characteristic = GetProp<string>(it, "AutomatCharReleaseType"),
                            current_scale = GetProp<string>(it, "CurrentScale"),
                            max_commutation = GetProp<double>(it, "MaxCommutation"),
                            category = GetProp<string>(it, "Category")
                        });
                    }
                    return new { success = true, count = list.Count, automats = list };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message, inner = ex.InnerException?.Message };
                }
            });
        }

        /// <summary>Каталог УЗО из активной БД оборудования.</summary>
        public object ListDbUzo()
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var (proxy, perr) = GetDbProxy();
                    if (proxy == null) return new { success = false, error = perr };

                    var uzoType = FindType("Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElUzo")!;
                    var items = LoadDbTable(proxy, uzoType, out var lerr);
                    if (items == null) return new { success = false, error = lerr };

                    var list = new List<object>();
                    foreach (var it in items)
                    {
                        if (it == null) continue;
                        list.Add(new
                        {
                            db_id = GetProp<int>(it, "DbId"),
                            name = GetProp<string>(it, "DbName"),
                            nominal_cur = GetProp<double>(it, "DbNominalCur"),
                            poles = GetProp<object>(it, "DbPoleCount")?.ToString(),
                            uzo_current_scale = GetProp<string>(it, "CurrentScaleUzo"),
                            category = GetProp<string>(it, "Category")
                        });
                    }
                    return new { success = true, count = list.Count, uzo = list };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message, inner = ex.InnerException?.Message };
                }
            });
        }

        /// <summary>
        /// Полноценное создание группы: щит + имя + автомат из БД (db_id) + опционально УЗО.
        /// </summary>
        public object CreateGroup(string boardAcId, string name, int automatDbId, int uzoDbId)
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var net = GetNet(out var err);
                    if (net == null) return new { success = false, error = err };

                    var board = FindNodeByAcId(net, boardAcId);
                    if (board == null)
                        return new { success = false, error = $"Щит {boardAcId} не найден в модели" };
                    if (board.GetType().FullName != BoardTypeName)
                        return new { success = false, error = $"Узел {boardAcId} не ElBoard" };

                    // Эталонный отходящий фидер (для FiderType / PhaseCount / FiderFilling)
                    object? refFider = null;
                    if (GetProp<object>(board, "OutFiders") is IEnumerable outs)
                        foreach (var f in outs) { refFider = f; break; }
                    if (refFider == null)
                        return new { success = false, error = "У щита нет отходящих фидеров — не с чего копировать параметры" };

                    var (proxy, perr) = GetDbProxy();
                    if (proxy == null) return new { success = false, error = perr };

                    // Автомат из БД (тихий поиск по DbId — SelectDbObject открывает
                    // модальный пикер, см. issue #5)
                    var automatType = FindType("Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElAutomat")!;
                    object? dbAutomat = null;
                    if (automatDbId > 0)
                    {
                        dbAutomat = FindDbObjectById(proxy, automatType, automatDbId, out var aerr);
                        if (dbAutomat == null)
                            return new { success = false, error = $"Автомат с DbId={automatDbId} не найден в БД ({aerr})" };
                    }

                    // УЗО из БД (опционально)
                    object? dbUzo = null;
                    if (uzoDbId > 0)
                    {
                        var uzoType = FindType("Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElUzo")!;
                        dbUzo = FindDbObjectById(proxy, uzoType, uzoDbId, out var uerr);
                        if (dbUzo == null)
                            return new { success = false, error = $"УЗО с DbId={uzoDbId} не найдено в БД ({uerr})" };
                    }

                    // Kit item
                    var kitType = FindType("Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElFiderKitItem")!;
                    var kit = Activator.CreateInstance(kitType)!;

                    var copied = new List<string>();
                    foreach (var (dst, srcName) in new[]
                        { ("FiderType", "FiderType"), ("PoleCount", "PhaseCount"), ("FiderFilling", "FiderFilling") })
                        if (CopyEnumValue(kit, dst, refFider, srcName))
                            copied.Add(dst);

                    SetPropValue(kit, "Text", string.IsNullOrWhiteSpace(name) ? "MCP" : name);
                    if (dbAutomat != null) { SetPropValue(kit, "SafeAutomat", dbAutomat); copied.Add("SafeAutomat<=БД"); }
                    else
                    {
                        var refAutomat = GetProp<object>(refFider, "SafeAutomat");
                        var refDb = refAutomat != null ? GetProp<object>(refAutomat, "Db") : null;
                        if (refDb != null) { SetPropValue(kit, "SafeAutomat", refDb); copied.Add("SafeAutomat<=эталон"); }
                    }
                    if (dbUzo != null) { SetPropValue(kit, "Uzo", dbUzo); copied.Add("Uzo<=БД"); }

                    // Создание
                    var container = GetContainer(out var cerr);
                    if (container == null) return new { success = false, error = cerr };
                    var craetor = ResolveInternal(container, FindType("Nanosoft.Electrica.IDbElFiderCraetor")!);
                    if (craetor == null)
                        return new { success = false, error = "IDbElFiderCraetor не резолвится" };

                    // Снимок AcId существующих фидеров — чтобы найти новый
                    var beforeIds = new HashSet<string>();
                    if (GetProp<object>(board, "OutFiders") is IEnumerable beforeOuts)
                        foreach (var f in beforeOuts)
                        {
                            var bid = GetProp<object>(f, "AcId")?.ToString();
                            if (bid != null) beforeIds.Add(bid);
                        }
                    int before = beforeIds.Count;

                    string createMsg;
                    try
                    {
                        craetor.GetType().GetMethod("CreateNewFider")!.Invoke(craetor, new[] { kit, board });
                        createMsg = "CreateNewFider OK";
                    }
                    catch (Exception ex)
                    {
                        return new { success = false, error = "CreateNewFider: " + (ex.InnerException?.Message ?? ex.Message), copied };
                    }

                    // Новый фидер = тот, чьего AcId не было в снимке
                    object? newFider = null;
                    if (GetProp<object>(board, "OutFiders") is IEnumerable afterOuts)
                        foreach (var f in afterOuts)
                        {
                            var aid = GetProp<object>(f, "AcId")?.ToString();
                            if (aid != null && !beforeIds.Contains(aid)) { newFider = f; break; }
                        }
                    int after = CollectionCount(GetProp<object>(board, "OutFiders"));

                    var steps = new List<string> { createMsg };
                    if (newFider == null)
                        steps.Add("Новый фидер не найден в OutFiders (diff по AcId пуст)");

                    // Привязка аппаратов по dbId. Модальный пикер открывал НЕ этот
                    // метод, а SelectDbObject (заменён на FindDbObjectById, issue #5);
                    // AddSafeAutomat/AddUzo, судя по разбору теста M4, неинтерактивны.
                    if (newFider != null && automatDbId > 0)
                    {
                        try
                        {
                            var m = newFider.GetType().GetMethod("AddSafeAutomat");
                            if (m == null) steps.Add("Метод AddSafeAutomat не найден у " + newFider.GetType().Name);
                            else { m.Invoke(newFider, new object[] { automatDbId }); steps.Add($"AddSafeAutomat({automatDbId}) вызван"); }
                        }
                        catch (Exception ex) { steps.Add("AddSafeAutomat: " + (ex.InnerException?.Message ?? ex.Message)); }
                    }
                    if (newFider != null && uzoDbId > 0)
                    {
                        try
                        {
                            var m = newFider.GetType().GetMethod("AddUzo");
                            if (m == null) steps.Add("Метод AddUzo не найден у " + newFider.GetType().Name);
                            else { m.Invoke(newFider, new object[] { uzoDbId }); steps.Add($"AddUzo({uzoDbId}) вызван"); }
                        }
                        catch (Exception ex) { steps.Add("AddUzo: " + (ex.InnerException?.Message ?? ex.Message)); }
                    }

                    // Проверка привязки: сверяем гаджет фидера с запрошенным DbId.
                    if (newFider != null && automatDbId > 0)
                        steps.Add(VerifyGadget(newFider, "SafeAutomat", automatDbId));
                    if (newFider != null && uzoDbId > 0)
                        steps.Add(VerifyGadget(newFider, "Uzo", uzoDbId));

                    // Имя группы — напрямую созданному фидеру
                    if (newFider != null && !string.IsNullOrWhiteSpace(name))
                    {
                        try
                        {
                            var tp = newFider.GetType().GetProperty("TitleName");
                            if (tp != null && tp.CanWrite && tp.PropertyType == typeof(string))
                            {
                                tp.SetValue(newFider, name);
                                steps.Add("TitleName установлен: " + name);
                            }
                            else steps.Add("TitleName недоступен для записи (CanWrite=" + (tp?.CanWrite.ToString() ?? "свойства нет") + ")");
                        }
                        catch (Exception ex) { steps.Add("TitleName: " + (ex.InnerException?.Message ?? ex.Message)); }
                    }

                    // Сохранение
                    var paperId = ExtractPaperId(boardAcId);
                    string saveMsg;
                    try
                    {
                        net.GetType().GetMethod("SaveObject")!.Invoke(net, new object?[] { board, true, paperId });
                        saveMsg = $"SaveObject(board) OK (paperId={paperId})";
                    }
                    catch (Exception ex)
                    {
                        saveMsg = "SaveObject: " + (ex.InnerException?.Message ?? ex.Message);
                    }

                    return new
                    {
                        success = true,
                        group_name = name,
                        automat_db_id = automatDbId,
                        uzo_db_id = uzoDbId,
                        copied,
                        steps,
                        out_fiders_before = before,
                        out_fiders_after = after,
                        new_fider_found = newFider != null,
                        new_fider_ac_id = newFider != null ? GetProp<object>(newFider, "AcId")?.ToString() : null,
                        save = saveMsg
                    };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message, inner = ex.InnerException?.Message };
                }
            });
        }

        /// <summary>
        /// Сверяет, что гаджет фидера (SafeAutomat/Uzo) привязан из БД
        /// с ожидаемым DbId (привязка выполняется CreateNewFider через kit-item).
        /// </summary>
        private static string VerifyGadget(object fider, string propName, int expectedDbId)
        {
            try
            {
                var gadget = fider.GetType().GetProperty(propName)?.GetValue(fider);
                if (gadget == null)
                    return $"{propName}: НЕ привязан (ожидался DbId={expectedDbId})";
                var db = gadget.GetType().GetProperty("Db")?.GetValue(gadget);
                int actualId = db != null
                    ? Convert.ToInt32(db.GetType().GetProperty("DbId")?.GetValue(db) ?? -1)
                    : -1;
                var title = gadget.GetType().GetProperty("TitleName")?.GetValue(gadget)?.ToString()
                            ?? gadget.GetType().GetProperty("Name")?.GetValue(gadget)?.ToString()
                            ?? gadget.GetType().Name;
                return actualId == expectedDbId
                    ? $"{propName} OK: {title} (DbId={actualId})"
                    : $"{propName}: привязан «{title}», но DbId={actualId} вместо {expectedDbId}";
            }
            catch (Exception ex)
            {
                return $"{propName}: проверка не удалась — {ex.InnerException?.Message ?? ex.Message}";
            }
        }

        /// <summary>
        /// Диагностика: все таблицы БД оборудования (типы Db* из Nanosoft.ObjectLib.ESN.Db)
        /// с количеством записей в активной БД. Помогает найти, где лежат УЗО/дифавтоматы.
        /// </summary>
        public object ListDbTables()
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var (proxy, perr) = GetDbProxy();
                    if (proxy == null) return new { success = false, error = perr };

                    var rows = new List<(string table, int count, string? error)>();
                    foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                    {
                        var an = asm.GetName().Name ?? "";
                        if (!an.StartsWith("Nanosoft", StringComparison.OrdinalIgnoreCase)) continue;
                        foreach (var t in SafeTypes(asm))
                        {
                            var fn = t.FullName ?? "";
                            if (!fn.StartsWith("Nanosoft.ObjectLib.ESN.Db.DbImpl.Db")
                                || t.IsAbstract || t.IsInterface) continue;
                            var items = LoadDbTable(proxy, t, out var lerr);
                            if (items == null) { rows.Add((t.Name, -1, lerr)); continue; }
                            int cnt = 0;
                            foreach (var _ in items) cnt++;
                            rows.Add((t.Name, cnt, null));
                        }
                    }
                    var tables = rows
                        .OrderByDescending(r => r.count)
                        .Select(r => r.error != null
                            ? (object)new { table = r.table, error = r.error }
                            : new { table = r.table, count = r.count })
                        .ToList();
                    return new { success = true, count = tables.Count, tables };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message, inner = ex.InnerException?.Message };
                }
            });
        }

        /// <summary>
        /// Расчёт мощности щита штатным конвейером Электро.
        /// Для каждого фидера: потребители (IElSupplyObject.GetConsumerData),
        /// нижестоящие объекты (GetSupplyCalcObjects), штатный расчёт
        /// (IPowerCalcObject.GetPowerCalculation с перебором значений enum-параметров).
        /// Если GetPowerCalculation у всех фидеров вернул null — фолбэк на
        /// IElPowerCalculator.CalculatePower(net, fiders, []), после чего
        /// расчётные поля читаются из самих фидеров (PcalcDp, IcalcDp, DeltaU...).
        /// </summary>
        public object CalculateBoardPower(string boardAcId)
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var net = GetNet(out var err);
                    if (net == null) return new { success = false, error = err };

                    var board = FindNodeByAcId(net, boardAcId);
                    if (board == null)
                        return new { success = false, error = $"Щит {boardAcId} не найден в модели" };
                    if (board.GetType().FullName != BoardTypeName)
                        return new { success = false, error = $"Узел {boardAcId} не ElBoard" };

                    // Фидеры щита с ролью (вводные/отходящие)
                    var fiders = new List<(object fider, string role)>();
                    foreach (var collName in new[] { "InputFiders", "OutFiders" })
                        if (GetProp<object>(board, collName) is IEnumerable coll)
                            foreach (var f in coll)
                                if (f != null)
                                    fiders.Add((f, collName == "InputFiders" ? "input" : "output"));

                    var results = new List<(object fider, string role, Dictionary<string, object?> data)>();
                    double sumPnom = 0;
                    bool anyCalc = false;
                    foreach (var (f, role) in fiders)
                    {
                        var d = (Dictionary<string, object?>)CalcOneSupplyObject(f, out var pnom, out _);
                        d["role"] = role;
                        if (pnom != null) sumPnom += pnom.Value;
                        if (d.ContainsKey("calc")) anyCalc = true;
                        results.Add((f, role, d));
                    }

                    // Фолбэк: штатный калькулятор, если GetPowerCalculation нигде не сработал
                    string? fallbackNote = null;
                    if (!anyCalc && fiders.Count > 0)
                        fallbackNote = RunPowerCalculatorFallback(net, fiders.Select(x => x.fider).ToList());

                    // Расчётные поля фидеров — читаем ПОСЛЕ фолбэка (он их и заполняет)
                    foreach (var (f, _, d) in results)
                    {
                        var fields = new Dictionary<string, object?>();
                        foreach (var pn in new[] { "PcalcDp", "IcalcDp", "IstartDp", "LeakI", "DeltaU", "Ikz2P", "Ikz3P" })
                        {
                            object? v;
                            try { v = f.GetType().GetProperty(pn)?.GetValue(f); }
                            catch { continue; }
                            if (v != null) fields[pn] = v.ToString();
                        }
                        if (fields.Count > 0) d["fields"] = fields;
                    }

                    // Итог по щиту: Pcalc вводных фидеров (они представляют весь щит);
                    // если вводных нет — сумма отходящих
                    double totalPcalc = 0;
                    var src = results.Where(r => r.role == "input").ToList();
                    if (src.Count == 0) src = results;
                    foreach (var r in src)
                        if (r.data.TryGetValue("fields", out var fo) && fo is Dictionary<string, object?> fd
                            && fd.TryGetValue("PcalcDp", out var pv))
                            totalPcalc += ParseRuNum(pv?.ToString()) ?? 0;

                    return new
                    {
                        success = true,
                        board = GetProp<string>(board, "TitleName"),
                        fiders_count = fiders.Count,
                        total_consumers_pnom = Math.Round(sumPnom, 3),
                        total_pcalc = Math.Round(totalPcalc, 3),
                        fallback_calculator = fallbackNote,
                        fiders = results.Select(r => (object)r.data).ToList()
                    };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message, inner = ex.InnerException?.Message };
                }
            });
        }

        /// <summary>
        /// Фолбэк-расчёт штатным IElPowerCalculator.CalculatePower(net, fiders, []):
        /// пересчитывает фидеры и заполняет их поля PcalcDp/IcalcDp/DeltaU/Ikz2P.
        /// Возвращает текстовый статус для диагностики.
        /// </summary>
        private string? RunPowerCalculatorFallback(object net, List<object> fiders)
        {
            try
            {
                var calcIface = FindTypeByName("IElPowerCalculator");
                if (calcIface == null) return "error: тип IElPowerCalculator не найден";
                var container = GetContainer(out var cerr);
                if (container == null) return "error: " + cerr;
                var calc = ResolveInternal(container, calcIface);
                if (calc == null) return "error: IElPowerCalculator не зарегистрирован";

                var mi = calc.GetType().GetMethods()
                    .FirstOrDefault(m => m.Name == "CalculatePower" && m.GetParameters().Length == 3);
                if (mi == null) return "error: 3-param CalculatePower не найден";
                var ps = mi.GetParameters();

                var fiderElem = ps[1].ParameterType.IsGenericType
                    ? ps[1].ParameterType.GetGenericArguments()[0] : typeof(object);
                var fiderList = (IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(fiderElem))!;
                foreach (var f in fiders)
                    if (fiderElem.IsInstanceOfType(f)) fiderList.Add(f);

                var objElem = ps[2].ParameterType.IsGenericType
                    ? ps[2].ParameterType.GetGenericArguments()[0] : typeof(object);
                var emptyList = (IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(objElem))!;

                mi.Invoke(calc, new object?[] { net, fiderList, emptyList });
                return $"ok: CalculatePower(List<{fiderElem.Name}>[{fiderList.Count}], List<{objElem.Name}>[0])";
            }
            catch (Exception ex)
            {
                return "error: " + (ex.InnerException?.Message ?? ex.Message);
            }
        }

        /// <summary>
        /// Разведка + расчёт одного объекта электроснабжения (фидер или щит):
        /// потребители через GetConsumerData(), нижестоящие объекты через
        /// GetSupplyCalcObjects(true), расчёт через GetPowerCalculation().
        /// Методы ищутся через интерфейсы — реализация в Электро явная (explicit).
        /// </summary>
        private static object CalcOneSupplyObject(object obj, out double? pnomSum, out double? pcalc)
        {
            pnomSum = null;
            pcalc = null;
            var d = new Dictionary<string, object?>
            {
                ["title"] = GetProp<string>(obj, "TitleName"),
                ["ac_id"] = GetProp<object>(obj, "AcId")?.ToString(),
                ["type"] = obj.GetType().Name
            };
            var t = obj.GetType();

            // 1. Подключённые потребители: IElSupplyObject.GetConsumerData()
            try
            {
                var mCons = FindIfaceMethod(t, "IElSupplyObject", "GetConsumerData", 0);
                if (mCons == null)
                {
                    d["consumers_count"] = -1;
                    d["consumers_error"] = t.GetInterfaces().Any(i => i.Name == "IElSupplyObject")
                        ? "метод GetConsumerData не найден в IElSupplyObject"
                        : "интерфейс IElSupplyObject не реализован";
                }
                else if (mCons.Invoke(obj, null) is IEnumerable cons)
                {
                    var list = new List<object>();
                    double sum = 0; int n = 0;
                    foreach (var c in cons)
                    {
                        if (c == null) continue;
                        n++;
                        var cd = new Dictionary<string, object?>
                        {
                            ["type"] = c.GetType().Name,
                            ["pnom"] = TryGetNum(c, "Pnom"),
                            ["cos_phi"] = TryGetNum(c, "CosPhi"),
                            ["kc"] = TryGetNum(c, "Kc")
                        };
                        var co = GetProp<object>(c, "ConsumerObject");
                        if (co != null)
                        {
                            cd["consumer_type"] = co.GetType().Name;
                            cd["consumer_title"] = GetProp<string>(co, "TitleName");
                            cd["consumer_acid"] = GetProp<object>(co, "AcId")?.ToString();
                        }
                        if (cd["pnom"] is double pv) sum += pv;
                        list.Add(cd);
                    }
                    d["consumers_count"] = n;
                    d["consumers_pnom_sum"] = Math.Round(sum, 3);
                    d["consumers"] = list;
                    pnomSum = sum;
                }
                else d["consumers_count"] = 0;
            }
            catch (Exception ex) { d["consumers_error"] = ex.InnerException?.Message ?? ex.Message; }

            // 2. Нижестоящие объекты электроснабжения: IElSupplyObject.GetSupplyCalcObjects(true)
            try
            {
                var mSup = FindIfaceMethod(t, "IElSupplyObject", "GetSupplyCalcObjects", 1);
                if (mSup != null && mSup.Invoke(obj, new object[] { true }) is IEnumerable sup)
                {
                    var list = new List<object>();
                    foreach (var s in sup)
                    {
                        if (s == null) continue;
                        list.Add(new Dictionary<string, object?>
                        {
                            ["type"] = s.GetType().Name,
                            ["title"] = GetProp<string>(s, "TitleName"),
                            ["ac_id"] = GetProp<object>(s, "AcId")?.ToString()
                        });
                    }
                    d["supply_objects_count"] = list.Count;
                    d["supply_objects"] = list;
                }
            }
            catch (Exception ex) { d["supply_error"] = ex.InnerException?.Message ?? ex.Message; }

            // 3. Штатный расчёт мощности: IPowerCalcObject.GetPowerCalculation(mode, calcMode)
            //    Перебираем ВСЕ значения обоих enum'ов: документированной комбинации нет,
            //    а от неподходящей метод возвращает null (проверено на model10).
            try
            {
                var mPc = FindIfaceMethod(t, "IPowerCalcObject", "GetPowerCalculation", 2);
                if (mPc == null)
                {
                    d["calc_error"] = t.GetInterfaces().Any(i => i.Name == "IPowerCalcObject")
                        ? "метод GetPowerCalculation не найден в IPowerCalcObject"
                        : "интерфейс IPowerCalcObject не реализован";
                }
                else
                {
                    var ps = mPc.GetParameters();
                    object? pcData = null;
                    string? usedArgs = null;
                    foreach (var v0 in Enum.GetValues(ps[0].ParameterType))
                    {
                        foreach (var v1 in Enum.GetValues(ps[1].ParameterType))
                        {
                            try
                            {
                                pcData = mPc.Invoke(obj, new object?[] { v0, v1 });
                                if (pcData != null) { usedArgs = $"{v0}, {v1}"; break; }
                            }
                            catch { }
                        }
                        if (pcData != null) break;
                    }
                    if (pcData != null)
                    {
                        var calc = new Dictionary<string, object?>
                        {
                            ["pc_type"] = pcData.GetType().Name,
                            ["calc_args"] = usedArgs
                        };
                        foreach (var pn in new[] { "Pinst", "Pcalc", "Icalc", "CosPhi", "Istart", "DeltaU",
                                                  "PinstNormal", "PcalcNormal", "IcalcNormal", "Kc", "Ksp" })
                        {
                            var v = TryGetNum(pcData, pn);
                            if (v != null) calc[pn] = v;
                        }
                        d["calc"] = calc;
                        pcalc = TryGetNum(pcData, "Pcalc");
                    }
                    else d["calc_error"] = "GetPowerCalculation вернул null на всех комбинациях параметров";
                }
            }
            catch (Exception ex) { d["calc_error"] = ex.InnerException?.Message ?? ex.Message; }

            return d;
        }

        /// <summary>Число из строки вида "155,36" или "155.36".</summary>
        private static double? ParseRuNum(string? s)
        {
            if (string.IsNullOrWhiteSpace(s)) return null;
            s = s.Trim();
            if (double.TryParse(s, out var v)) return v;
            if (double.TryParse(s.Replace(',', '.'),
                    System.Globalization.NumberStyles.Any,
                    System.Globalization.CultureInfo.InvariantCulture, out v)) return v;
            return null;
        }
        /// <summary>
        /// Метод интерфейса по коротким именам интерфейса и метода.
        /// Работает и при явной (explicit) реализации — когда метод приватный
        /// и через GetMethods() класса не виден. Вызов interface MethodInfo
        /// на объекте-реализации корректен.
        /// </summary>
        private static MethodInfo? FindIfaceMethod(Type t, string ifaceShortName, string methodName, int paramCount)
        {
            foreach (var i in t.GetInterfaces())
                if (i.Name == ifaceShortName)
                    return i.GetMethods().FirstOrDefault(m => m.Name == methodName && m.GetParameters().Length == paramCount)
                        ?? i.GetMethods().FirstOrDefault(m => m.Name == methodName);
            return null;
        }

        /// <summary>Числовое значение свойства; умеет разворачивать DesignParameter-подобные обёртки.</summary>
        private static double? TryGetNum(object obj, string prop)
        {
            try
            {
                var v = obj.GetType().GetProperty(prop)?.GetValue(obj);
                if (v == null) return null;
                if (v is double dv) return Math.Round(dv, 4);
                if (v is float fv) return Math.Round((double)fv, 4);
                if (v is int iv) return iv;
                if (v is decimal dec) return (double)dec;
                var inner = v.GetType().GetProperty("Value")?.GetValue(v)
                         ?? v.GetType().GetProperty("Val")?.GetValue(v);
                if (inner is double idv) return Math.Round(idv, 4);
                return double.TryParse(v.ToString(), out var parsed) ? parsed : (double?)null;
            }
            catch { return null; }
        }

        private static Type? FindTypeByName(string shortName)
        {
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                foreach (var t in SafeTypes(asm))
                    if (t.Name == shortName) return t;
            return null;
        }

        // ── Доступ к БД оборудования ────────────────────────

        private (object? proxy, string? error) GetDbProxy()
        {
            var container = GetContainer(out var cerr);
            if (container == null) return (null, cerr);
            var proxyType = FindType("Nanosoft.CAE.Db.DatabaseProxyComponent.IDatabaseProxyComponent");
            if (proxyType == null) return (null, "Тип IDatabaseProxyComponent не найден");
            object? proxy = null;
            try { proxy = ResolveInternal(container, proxyType); } catch (Exception ex) { return (null, ex.InnerException?.Message ?? ex.Message); }
            if (proxy == null) return (null, "IDatabaseProxyComponent не зарегистрирован в контейнере");
            return (proxy, null);
        }

        /// <summary>
        /// Находит запись БД оборудования по DbId через LoadTypedSource — тихо, без UI.
        /// SelectDbObject(Type, int) НЕ использовать: он открывает модальный пикер
        /// «База данных оборудования» и висит до клика пользователя (issue #5).
        /// </summary>
        private static object? FindDbObjectById(object proxy, Type tableType, int dbId, out string? error)
        {
            error = null;
            var items = LoadDbTable(proxy, tableType, out error);
            if (items == null) return null;
            foreach (var it in items)
            {
                if (it == null) continue;
                try
                {
                    var v = it.GetType().GetProperty("DbId")?.GetValue(it);
                    if (v != null && Convert.ToInt32(v) == dbId) return it;
                }
                catch { }
            }
            error = $"Запись с DbId={dbId} не найдена в {tableType.Name}";
            return null;
        }

        private static IEnumerable<object?>? LoadDbTable(object proxy, Type tableType, out string? error)
        {
            error = null;
            try
            {
                var db = proxy.GetType().GetMethod("GetDb")!.Invoke(proxy, new object[] { tableType });
                if (db == null) { error = "GetDb вернул null (нет активной БД оборудования?)"; return null; }
                var load = db.GetType().GetMethods()
                    .FirstOrDefault(m => m.Name == "LoadTypedSource" && m.IsGenericMethodDefinition && m.GetParameters().Length == 0);
                if (load == null) { error = "LoadTypedSource<T>() не найден у IDataSource"; return null; }
                var arr = load.MakeGenericMethod(tableType).Invoke(db, null);
                if (arr is IEnumerable en) return en.Cast<object?>();
                error = "LoadTypedSource вернул не-коллекцию";
                return null;
            }
            catch (Exception ex)
            {
                error = ex.InnerException?.Message ?? ex.Message;
                return null;
            }
        }

        // ── Утилиты создания ────────────────────────────────

        private static object? FindNodeByAcId(object net, string acId)
        {
            if (net.GetType().GetProperty("Nodes")?.GetValue(net) is IEnumerable nodes)
                foreach (var node in nodes)
                {
                    if (node == null) continue;
                    if (GetProp<object>(node, "AcId")?.ToString() == acId)
                        return node;
                }
            return null;
        }

        private static bool CopyEnumValue(object dst, string dstProp, object src, string srcProp)
        {
            try
            {
                var sv = src.GetType().GetProperty(srcProp)?.GetValue(src);
                if (sv is not Enum) return false;
                var dp = dst.GetType().GetProperty(dstProp);
                if (dp == null || !dp.CanWrite) return false;
                var converted = Enum.ToObject(dp.PropertyType, Convert.ToInt64(sv));
                dp.SetValue(dst, converted);
                return true;
            }
            catch { return false; }
        }

        private static void SetPropValue(object obj, string name, object? value)
        {
            try
            {
                var p = obj.GetType().GetProperty(name);
                if (p == null || !p.CanWrite || value == null) return;
                if (!p.PropertyType.IsInstanceOfType(value) && p.PropertyType != value.GetType()) return;
                p.SetValue(obj, value);
            }
            catch { }
        }

        private static int ExtractPaperId(string acId)
        {
            try { return int.Parse(acId.Split(':')[0]); }
            catch { return 0; }
        }

        // ── Доступ к контейнеру ─────────────────────────────

        private object? GetContainer(out string? error)
        {
            error = null;
            if (_container != null) return _container;

            foreach (var asm in NanosoftAssemblies())
            {
                foreach (var t in SafeTypes(asm))
                {
                    foreach (var (getter, source) in StaticGetters(t, ContainerTypeName))
                    {
                        object? v;
                        try { v = getter(); }
                        catch { continue; }
                        if (v == null) continue;
                        if (v.GetType().GetMethods().Any(m => m.Name == "Resolve"))
                        {
                            _container = v;
                            _containerSource = source;
                            return v;
                        }
                    }
                }
            }
            error = "Экземпляр IContainer не найден среди статических членов Nanosoft-сборок";
            return null;
        }

        private static object? ResolveInternal(object container, Type t)
        {
            var resolve = container.GetType().GetMethods()
                .FirstOrDefault(m => m.Name == "Resolve" && !m.IsGenericMethod
                    && m.GetParameters() is { Length: 1 } ps
                    && ps[0].ParameterType == typeof(Type));
            if (resolve == null)
                throw new InvalidOperationException("У контейнера нет метода Resolve(Type)");
            return resolve.Invoke(container, new object[] { t });
        }

        // ── Доступ к сети модели ────────────────────────────

        private object? GetNet(out string? error)
        {
            error = null;
            if (_net != null) return _net;

            // Стратегия A: статический акцессор IAcadNet
            foreach (var asm in NanosoftAssemblies())
            {
                foreach (var t in SafeTypes(asm))
                {
                    foreach (var (getter, source) in StaticGetters(t, NetTypeName))
                    {
                        object? v;
                        try { v = getter(); }
                        catch { continue; }
                        if (v != null)
                        {
                            _net = v;
                            _netSource = "static: " + source;
                            return v;
                        }
                    }
                }
            }

            // Стратегия B: IAcadNet зарегистрирована в контейнере (per-project scope)
            var container = GetContainer(out _);
            var netType = FindType(NetTypeName);
            if (container != null && netType != null)
            {
                object? v = null;
                try { v = ResolveInternal(container, netType); } catch { }
                if (v != null)
                {
                    _net = v;
                    _netSource = "container.Resolve(IAcadNet)";
                    return v;
                }
            }

            // Стратегия C: фабрика + загрузка текущего документа
            var factoryType = FindType(NetFactoryTypeName);
            if (container != null && factoryType != null)
            {
                object? factory = null;
                try { factory = ResolveInternal(container, factoryType); } catch { }
                var net = factory?.GetType().GetMethod("NewNet")?.Invoke(factory, null);
                if (net != null)
                {
                    try { net.GetType().GetMethod("LoadCurrentDocument")?.Invoke(net, null); } catch { }
                    _net = net;
                    _netSource = "IAcadNetFactory.NewNet() + LoadCurrentDocument()";
                    return net;
                }
            }

            error = "IAcadNet не получена: нет ни статического акцессора, ни регистрации в контейнере, ни фабрики";
            return null;
        }

        // ── Рефлексионные утилиты ───────────────────────────

        private static IEnumerable<Assembly> NanosoftAssemblies() =>
            AppDomain.CurrentDomain.GetAssemblies()
                .Where(a => (a.GetName().Name ?? "").StartsWith("Nanosoft", StringComparison.OrdinalIgnoreCase));

        private static Type? FindType(string fullName)
        {
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type? t;
                try { t = asm.GetType(fullName); }
                catch { continue; }
                if (t != null) return t;
            }
            return null;
        }

        private static IEnumerable<Type> SafeTypes(Assembly asm)
        {
            Type[] types;
            try { types = asm.GetTypes(); }
            catch (ReflectionTypeLoadException ex) { types = ex.Types.Where(t => t != null).Cast<Type>().ToArray(); }
            catch { yield break; }
            foreach (var t in types)
                if (t != null) yield return t;
        }

        private static readonly HashSet<string> TargetAccessorTypes = new()
        {
            ContainerTypeName,
            NetTypeName,
            NetFactoryTypeName,
            "Nanosoft.Platform.Platform.IScopeComponentManager"
        };

        private static IEnumerable<object> InterestingStaticMembers(Type t)
        {
            const BindingFlags flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
            PropertyInfo[] props;
            FieldInfo[] fields;
            try
            {
                props = t.GetProperties(flags);
                fields = t.GetFields(flags);
            }
            catch { yield break; }

            foreach (var p in props)
            {
                string? tn;
                try { tn = p.PropertyType.FullName; }
                catch { continue; }
                if (tn != null && TargetAccessorTypes.Contains(tn))
                    yield return new { holder = t.FullName, member = p.Name, kind = "static property", type = tn };
            }
            foreach (var f in fields)
            {
                string? tn;
                try { tn = f.FieldType.FullName; }
                catch { continue; }
                if (tn != null && TargetAccessorTypes.Contains(tn))
                    yield return new { holder = t.FullName, member = f.Name, kind = "static field", type = tn };
            }
        }

        private static IEnumerable<(Func<object?> getter, string source)> StaticGetters(Type t, string typeFullName)
        {
            const BindingFlags flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
            PropertyInfo[] props;
            FieldInfo[] fields;
            try
            {
                props = t.GetProperties(flags);
                fields = t.GetFields(flags);
            }
            catch { yield break; }

            foreach (var p in props)
            {
                if (p.PropertyType.FullName != typeFullName || p.GetIndexParameters().Length > 0) continue;
                var prop = p;
                yield return (() => prop.GetValue(null), $"{t.FullName}.{p.Name}");
            }
            foreach (var f in fields)
            {
                if (f.FieldType.FullName != typeFullName) continue;
                var field = f;
                yield return (() => field.GetValue(null), $"{t.FullName}.{f.Name}");
            }
        }

        private static T? GetProp<T>(object obj, string name)
        {
            try
            {
                var v = obj.GetType().GetProperty(name)?.GetValue(obj);
                return v is T tv ? tv : default;
            }
            catch { return default; }
        }

        private static int CollectionCount(object? col)
        {
            if (col == null) return -1;
            try
            {
                if (col is ICollection c) return c.Count;
                var p = col.GetType().GetProperty("Count");
                if (p != null) return Convert.ToInt32(p.GetValue(col));
            }
            catch { }
            return -1;
        }

        private static object DescribeNode(object node) => new
        {
            title = GetProp<string>(node, "TitleName"),
            ac_id = GetProp<object>(node, "AcId")?.ToString(),
            type = node.GetType().FullName
        };

        private static object DumpNodeDeep(object node, int depth)
        {
            var t = node.GetType();
            var values = new Dictionary<string, object?>();
            foreach (var p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance))
            {
                if (p.GetIndexParameters().Length > 0 || !p.CanRead) continue;
                object? v;
                try { v = p.GetValue(node); }
                catch (Exception ex) { values[p.Name] = $"<err: {ex.Message}>"; continue; }
                values[p.Name] = SafeVal(v, depth);
            }
            return new Dictionary<string, object?>
            {
                ["success"] = true,
                ["type"] = t.FullName,
                ["title"] = GetProp<string>(node, "TitleName"),
                ["ac_id"] = GetProp<object>(node, "AcId")?.ToString(),
                ["properties_count"] = values.Count,
                ["properties"] = values
            };
        }

        private static object? SafeVal(object? v, int depth)
        {
            if (v == null) return null;
            var t = v.GetType();
            if (t.IsPrimitive || v is string || v is decimal) return v;
            if (t.FullName == "Nanosoft.Acad.GlobalId") return v.ToString();
            if (v is Enum) return $"{v} ({Convert.ToInt64(v)})";
            if (v is IDictionary dict) return $"[dict count={dict.Count}]";
            if (v is ICollection col) return $"[{t.Name} count={col.Count}]";
            if (v is IEnumerable) return $"[{t.Name}]";
            var title = GetProp<string>(v, "TitleName");
            if (title != null) return $"[{t.Name}] {title}";
            if (depth < 1 && (t.FullName ?? "").StartsWith("Nanosoft"))
                return DumpNodeDeep(v, depth + 1);
            return $"[{t.Name}] {v}";
        }
    }
}
