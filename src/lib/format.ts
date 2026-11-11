export function formatPublishedDate(isoDate: string) {
  const [year, month, day] = isoDate.split("-");
  return `${year}.${month}.${day}`;
}

export function seoulDateTime(isoDate: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) return isoDate;
  return `${isoDate}T09:00:00+09:00`;
}
