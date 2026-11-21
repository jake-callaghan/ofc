export function runningTime(createdAt, now = Date.now()) {
  const minutes = Math.max(0, Math.floor((now - createdAt * 1000) / 60000));
  if (minutes === 0) return '<1m';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${minutes % 60}m`;
  return `${Math.floor(hours / 24)}d ${hours % 24}h`;
}
