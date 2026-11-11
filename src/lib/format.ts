export function formatPublishedDate(isoDate: string) {
  const [year, month, day] = isoDate.split("-");
  return `${year}.${month}.${day}`;
}
