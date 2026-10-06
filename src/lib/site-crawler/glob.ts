function globToRegex(glob: string): RegExp {
  const escaped = glob
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, ".*")
    .replace(/\?/g, ".");
  return new RegExp(`^${escaped}$`, "i");
}

export function matchesGlob(str: string, pattern: string): boolean {
  if (!pattern) return true;
  return globToRegex(pattern).test(str);
}

export function filterUrlsByGlob(
  urls: string[],
  includePatterns: string[],
  excludePatterns: string[]
): string[] {
  return urls.filter((url) => {
    let path = url;
    try {
      path = new URL(url).pathname;
    } catch {
      // Use full string if not valid URL
    }

    if (excludePatterns.length > 0) {
      const excluded = excludePatterns.some(
        (pat) => matchesGlob(path, pat) || matchesGlob(url, pat)
      );
      if (excluded) return false;
    }

    if (includePatterns.length > 0) {
      const included = includePatterns.some(
        (pat) => matchesGlob(path, pat) || matchesGlob(url, pat)
      );
      if (!included) return false;
    }

    return true;
  });
}
