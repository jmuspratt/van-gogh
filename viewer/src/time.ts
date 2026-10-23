// Simulation time is measured in days since 1 January 1870 (UTC), as a float.

const EPOCH = Date.UTC(1870, 0, 1);
const DAY = 86_400_000;

export const toDay = (iso: string) => (Date.parse(iso + "T00:00:00Z") - EPOCH) / DAY;

export const fromDay = (day: number) => new Date(EPOCH + day * DAY);

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export function formatDay(day: number): { year: string; month: string; full: string } {
  const d = fromDay(day);
  const month = MONTHS[d.getUTCMonth()];
  return { year: String(d.getUTCFullYear()), month, full: `${d.getUTCDate()} ${month} ${d.getUTCFullYear()}` };
}

/** Month index since Jan 1870, for histograms. */
export const monthIndex = (day: number) => {
  const d = fromDay(day);
  return (d.getUTCFullYear() - 1870) * 12 + d.getUTCMonth();
};
