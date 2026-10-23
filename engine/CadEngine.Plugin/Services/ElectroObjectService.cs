using System;
using System.Collections.Generic;
using System.Linq;
using Multicad;
using Multicad.DatabaseServices;
using Multicad.CustomObjectBase;
using Teigha.DatabaseServices;
using HostMgd.ApplicationServices;
using App = HostMgd.ApplicationServices.Application;

namespace CadEngine.Services
{
    /// <summary>
    /// Диагностика и чтение объектов nanoCAD BIM Электро.
    /// Работает через универсальный канал платформы (ObjectFilter + ObjectProperties),
    /// без compile-time зависимости от сборок Электро:
    /// тип объекта определяется рефлексией, свойства читаются по именам.
    /// </summary>
    public class ElectroObjectService
    {
        /// <summary>
        /// Список всех пользовательских объектов (McCustomBase — к ним относятся
        /// объекты вертикальных решений, включая Электро) в текущем документе.
        /// </summary>
        public object ListElectroObjects()
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var items = new List<object>();
                    var ids = ObjectFilter.Create(true).GetObjects();
                    foreach (var id in ids)
                    {
                        var obj = id.GetObject();
                        if (obj is not McCustomBase)
                            continue;

                        items.Add(new
                        {
                            handle = HandleOf(id),
                            type = obj.GetType().FullName,
                            assembly = obj.GetType().Assembly.GetName().Name,
                            is_electro = IsElectroType(obj.GetType())
                        });
                    }

                    var electro = items.Where(i => ((dynamic)i).is_electro == true).ToList();
                    return new
                    {
                        success = true,
                        total_custom_objects = items.Count,
                        electro_objects = electro.Count,
                        objects = electro.Count > 0 ? electro : items,
                        note = electro.Count > 0
                            ? "Отфильтрованы объекты Электро (namespace содержит Electrica/ESN)"
                            : "Объекты Электро не найдены; возвращены все пользовательские объекты"
                    };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message };
                }
            });
        }

        /// <summary>
        /// Полный дамп объекта по handle: тип, сборка, все свойства ObjectProperties.
        /// Ключевой диагностический инструмент этапа PoC.
        /// </summary>
        public object DumpObject(string handle)
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var id = McObjectId.FromHandle(Convert.ToInt64(handle, 16));
                    var obj = id.GetObject();
                    if (obj == null)
                        return new { success = false, error = $"Объект с handle {handle} не найден" };

                    return DumpSingle(id, obj);
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message };
                }
            });
        }

        /// <summary>
        /// Дамп объектов, выбранных пользователем в nanoCAD (implied selection).
        /// </summary>
        public object DumpSelection()
        {
            return MainThreadExecutor.Execute(() =>
            {
                try
                {
                    var doc = App.DocumentManager.MdiActiveDocument;
                    if (doc == null)
                        return new { success = false, error = "Нет активного документа" };

                    var sel = doc.Editor.SelectImplied();
                    if (sel.Status != HostMgd.EditorInput.PromptStatus.OK || sel.Value.Count == 0)
                        return new { success = false, error = "Нет выбранных объектов. Выделите объекты в nanoCAD и повторите." };

                    var result = new List<object>();
                    var db = HostApplicationServices.WorkingDatabase;
                    foreach (HostMgd.EditorInput.SelectedObject so in sel.Value)
                    {
                        // ObjectId → Handle → McObjectId (FromOldId недоступен в NC26)
                        long handleValue;
                        using (var tr = db.TransactionManager.StartTransaction())
                        {
                            var ent = tr.GetObject(so.ObjectId, OpenMode.ForRead) as Entity;
                            if (ent == null) { tr.Commit(); continue; }
                            handleValue = ent.Handle.Value;
                            tr.Commit();
                        }
                        var mcId = McObjectId.FromHandle(handleValue);
                        var obj = mcId.GetObject();
                        if (obj == null) continue;
                        result.Add(DumpSingle(mcId, obj));
                    }
                    return new { success = true, count = result.Count, objects = result };
                }
                catch (Exception ex)
                {
                    return new { success = false, error = ex.Message };
                }
            });
        }

        // ── Внутреннее ──────────────────────────────────────

        private object DumpSingle(McObjectId id, McObject obj)
        {
            var t = obj.GetType();
            var dump = new Dictionary<string, object?>
            {
                ["handle"] = HandleOf(id),
                ["type"] = t.FullName,
                ["assembly"] = t.Assembly.GetName().Name,
                ["base_type"] = t.BaseType?.FullName,
                ["is_custom_object"] = obj is McCustomBase
            };

            // Свойства объекта через универсальный механизм платформы:
            // DbEntity есть у McEntity (а не у базового McObject)
            try
            {
                McProperties? props = (obj as McEntity)?.DbEntity?.ObjectProperties;
                if (props != null)
                {
                    var names = props.GetNames();
                    var values = new Dictionary<string, object?>();
                    foreach (var name in names)
                    {
                        try
                        {
                            var v = props[name];
                            values[name] = SafeValue(v);
                        }
                        catch (Exception ex)
                        {
                            values[name] = $"<ошибка чтения: {ex.Message}>";
                        }
                    }
                    dump["properties"] = values;
                    dump["properties_count"] = values.Count;
                }
                else
                {
                    dump["properties"] = null;
                    dump["note"] = "ObjectProperties недоступны для этого объекта";
                }
            }
            catch (Exception ex)
            {
                dump["properties_error"] = ex.Message;
            }

            return dump;
        }

        private static object? SafeValue(object? v)
        {
            if (v == null) return null;
            var t = v.GetType();
            if (t.IsPrimitive || v is string || v is decimal) return v;
            if (v is Enum) return v.ToString();
            // Сложные значения (ссылки на другие объекты, коллекции) — строкой
            return $"[{t.Name}] {v}";
        }

        private static bool IsElectroType(Type t)
        {
            var ns = t.FullName ?? "";
            var asm = t.Assembly.GetName().Name ?? "";
            return ns.Contains("Electrica") || ns.Contains("ESN")
                || asm.Contains("Electrica") || asm.Contains("ESN");
        }

        private static string HandleOf(McObjectId id)
        {
            id.ToHandle(out long h, out _);
            return h.ToString("X");
        }
    }
}
