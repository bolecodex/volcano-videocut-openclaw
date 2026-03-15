const FILE_RAW = "/api/workspace/file-raw?path=";

function fileRawUrl(relativePath: string): string {
  return `${FILE_RAW}${encodeURIComponent(relativePath)}`;
}

/**
 * Normalize a relative path: strip leading "./" and collapse redundant slashes.
 */
function normalizePath(p: string): string {
  return p.replace(/^\.\//, "").replace(/\/+/g, "/");
}

/**
 * Resolve an image source: prefer local path, fallback to remote URL.
 * @param project - project name
 * @param imageUrl - remote URL (may expire)
 * @param imagePath - local relative path (may start with "./" for project-relative)
 * @param pathPrefix - prefix relative to project, e.g. "shots/" for shot images
 */
export function resolveImageSrc(
  project: string,
  imageUrl?: string,
  imagePath?: string,
  pathPrefix = "",
): string | undefined {
  if (imagePath) {
    const clean = normalizePath(imagePath);
    const alreadyPrefixed =
      pathPrefix && clean.startsWith(pathPrefix.replace(/\/$/, ""));
    const full = alreadyPrefixed || !pathPrefix
      ? `${project}/${clean}`
      : `${project}/${pathPrefix}${clean}`;
    return fileRawUrl(normalizePath(full));
  }
  return imageUrl || undefined;
}

/**
 * Resolve an audio source: prefer local path, fallback to remote URL.
 */
export function resolveAudioSrc(
  project: string,
  audioUrl?: string,
  audioPath?: string,
): string | undefined {
  if (audioPath) {
    return fileRawUrl(normalizePath(`${project}/${audioPath}`));
  }
  return audioUrl || undefined;
}
