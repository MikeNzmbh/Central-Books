export const parseCookies = (cookieString: string): Record<string, string> => {
  return cookieString.split(";").reduce((acc, part) => {
    const [rawKey, ...rest] = part.trim().split("=");
    if (!rawKey) return acc;
    acc[decodeURIComponent(rawKey)] = decodeURIComponent(rest.join("="));
    return acc;
  }, {} as Record<string, string>);
};
