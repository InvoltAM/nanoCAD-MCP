using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

namespace CadEngine.Services
{
    /// <summary>
    /// Рефлексия по сборкам, загруженным в процесс nanoCAD.
    /// Инструмент разведки API Электро в рантайме: список сборок,
    /// типов, сигнатур методов. Не требует CAD-объектов — выполняется сразу.
    /// </summary>
    public class ElectroInspectService
    {
        /// <summary>Загруженные сборки, отфильтрованные по подстроке имени.</summary>
        public object ListAssemblies(string filter)
        {
            try
            {
                var asms = AppDomain.CurrentDomain.GetAssemblies()
                    .Where(a => string.IsNullOrEmpty(filter)
                        || (a.GetName().Name ?? "").Contains(filter, StringComparison.OrdinalIgnoreCase))
                    .OrderBy(a => a.GetName().Name)
                    .Select(a =>
                    {
                        string loc;
                        try { loc = a.IsDynamic ? "<dynamic>" : a.Location; }
                        catch { loc = "<n/a>"; }
                        return new
                        {
                            name = a.GetName().Name,
                            version = a.GetName().Version?.ToString(),
                            location = loc
                        };
                    })
                    .ToList();
                return new { success = true, count = asms.Count, assemblies = asms };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        /// <summary>Публичные типы сборки (имя сборки без .dll).</summary>
        public object ListTypes(string assemblyName)
        {
            try
            {
                var asm = FindAssembly(assemblyName);
                if (asm == null)
                    return new { success = false, error = $"Сборка {assemblyName} не загружена" };

                Type[] types;
                try { types = asm.GetTypes(); }
                catch (ReflectionTypeLoadException ex) { types = ex.Types.Where(t => t != null).ToArray()!; }

                var list = types
                    .Where(t => t.IsPublic)
                    .OrderBy(t => t.FullName)
                    .Select(t => new
                    {
                        name = t.FullName,
                        kind = t.IsInterface ? "interface" : t.IsEnum ? "enum" : t.IsAbstract && t.IsSealed ? "static" : "class",
                        base_type = t.BaseType?.Name
                    })
                    .ToList();
                return new { success = true, count = list.Count, types = list };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        /// <summary>Методы и свойства типа с полными сигнатурами.</summary>
        public object DumpType(string fullName)
        {
            try
            {
                // Ищем тип во всех загруженных сборках
                Type? t = null;
                foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    try { t = asm.GetType(fullName); } catch { }
                    if (t != null) break;
                }
                if (t == null)
                    return new { success = false, error = $"Тип {fullName} не найден" };

                var flags = BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;

                var props = t.GetProperties(flags).Select(p =>
                    $"{TypeName(p.PropertyType)} {p.Name} {{ {(p.CanRead ? "get;" : "")}{(p.CanWrite ? " set;" : "")} }}").ToList();

                var ctors = t.GetConstructors(flags).Select(c =>
                    $".ctor({Params(c.GetParameters())})").ToList();

                var methods = t.GetMethods(flags)
                    .Where(m => !m.IsSpecialName)
                    .Select(m => $"{TypeName(m.ReturnType)} {m.Name}({Params(m.GetParameters())}){(m.IsStatic ? " [static]" : "")}")
                    .ToList();

                return new
                {
                    success = true,
                    type = t.FullName,
                    assembly = t.Assembly.GetName().Name,
                    base_type = t.BaseType?.FullName,
                    interfaces = t.GetInterfaces().Select(i => i.Name).ToList(),
                    constructors = ctors,
                    properties = props,
                    methods = methods
                };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        /// <summary>Типы с атрибутом Component/Composer — карта DI-контейнера Электро.</summary>
        public object ListComponents(string assemblyName)
        {
            try
            {
                var asm = FindAssembly(assemblyName);
                if (asm == null)
                    return new { success = false, error = $"Сборка {assemblyName} не загружена" };

                Type[] types;
                try { types = asm.GetTypes(); }
                catch (ReflectionTypeLoadException ex) { types = ex.Types.Where(t => t != null).ToArray()!; }

                var list = new List<object>();
                foreach (var t in types)
                {
                    object[] attrs;
                    try { attrs = t.GetCustomAttributes(false); } catch { continue; }
                    var names = attrs.Select(a => a.GetType().Name)
                        .Where(n => n.Contains("Component") || n.Contains("Composer") || n.Contains("Service"))
                        .ToList();
                    if (names.Count > 0)
                        list.Add(new { type = t.FullName, attributes = names });
                }
                return new { success = true, count = list.Count, components = list };
            }
            catch (Exception ex)
            {
                return new { success = false, error = ex.Message };
            }
        }

        // ── Внутреннее ──────────────────────────────────────

        private static Assembly? FindAssembly(string name) =>
            AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(a => string.Equals(a.GetName().Name, name, StringComparison.OrdinalIgnoreCase));

        private static string Params(ParameterInfo[] ps) =>
            string.Join(", ", ps.Select(p => $"{TypeName(p.ParameterType)} {p.Name}"));

        private static string TypeName(Type t)
        {
            if (!t.IsGenericType) return t.Name;
            var args = string.Join(",", t.GetGenericArguments().Select(TypeName));
            return $"{t.Name.Split('`')[0]}<{args}>";
        }
    }
}
