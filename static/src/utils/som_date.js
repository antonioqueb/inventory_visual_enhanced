/** @odoo-module **/
/**
 * Formato de fecha único del sistema: "13 ago 2026" (con hora opcional).
 *
 * Solo para ETIQUETAS que ve el usuario. Cualquier fecha que viaje como dato
 * (clave de agrupación, valor a ordenar, dominio, payload al backend, valor de
 * un <input type="date">) se queda en ISO: este formato NO se puede volver a
 * convertir a fecha.
 *
 * Parsea la cadena SIN construir un Date: new Date("2026-08-13") se interpreta
 * como UTC y en México mostraría el día ANTERIOR.
 */

const MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun",
                  "jul", "ago", "sep", "oct", "nov", "dic"];

export function somFormatDate(value, options) {
    const opts = options || {};
    const empty = opts.empty !== undefined ? opts.empty : "—";
    if (!value) return empty;
    let raw = "";
    if (typeof value === "string") {
        raw = value.trim();
    } else if (value instanceof Date && !isNaN(value)) {
        const p2 = (n) => String(n).padStart(2, "0");
        raw = `${value.getFullYear()}-${p2(value.getMonth() + 1)}-${p2(value.getDate())}` +
              ` ${p2(value.getHours())}:${p2(value.getMinutes())}`;
    }
    if (!raw) return empty;
    const [datePart, timePart] = raw.split(/[ T]/);
    const parts = datePart.split("-");
    if (parts.length !== 3) return raw;
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10);
    const day = parseInt(parts[2], 10);
    if (!year || !month || !day || month < 1 || month > 12) return raw;
    let out = `${String(day).padStart(2, "0")} ${MESES_ES[month - 1]} ${year}`;
    if (opts.withTime && timePart) out += ` ${timePart.slice(0, 5)}`;
    return out;
}
