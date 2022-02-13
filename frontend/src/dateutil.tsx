
export const parseYmd = (date: string) => {
    const [y, m, d] = date.split("-").map((v) => parseInt(v));
    return new Date(y, m - 1, d);
}

export const WEEKDAY_I18N = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"];
export const MONTH_I18N = ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september", "oktober", "november", "december"];

export const weekdayI18n = (date: Date) => WEEKDAY_I18N[(date.getDay() + 6) % 7];
export const fulldateI18n = (date: Date) => `${date.getDate()}. ${MONTH_I18N[date.getMonth()]} ${date.getFullYear()}`

export const toIsoDate = (date: Date) => {
    const m = "0" + (date.getMonth() + 1);
    const d = "0" + (date.getDate());
    return date.getFullYear() + "-" + m.slice(-2) + "-" + d.slice(-2);
}
