export function isPublicBackendHealthPath(path: string[]): boolean {
  const normalized = path.join("/");
  return normalized === "livez" || normalized === "readyz";
}
