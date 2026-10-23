using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

namespace CadEngine.Services
{
    /// <summary>
    /// Доступ к CAE-модели nanoCAD BIM Электро: DI-контейнер (Nanosoft.Platform),
    /// сеть модели (IAcadNet) и её узлы (щиты, фидеры, потребители).
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
        /// Ключевой инструмент перед созданием объектов: показывает фактические
        /// значения, которые Электро хранит в реальных узлах.
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
