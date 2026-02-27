export function decodeJwt(token) {
  if (!token || typeof token !== "string") return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const payload = parts[1]
      .replace(/-/g, "+")
      .replace(/_/g, "/")
      .padEnd(Math.ceil(parts[1].length / 4) * 4, "=");
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
}

export function isTokenExpired(token) {
  const decoded = decodeJwt(token);
  if (!decoded?.exp) return true;
  const now = Math.floor(Date.now() / 1000);
  return decoded.exp <= now;
}
