import { useState, useCallback } from "react";
import { ImageOff } from "lucide-react";

interface FallbackImageProps
  extends React.ImgHTMLAttributes<HTMLImageElement> {
  fallbackIcon?: React.ReactNode;
  fallbackClassName?: string;
}

/**
 * An <img> wrapper that gracefully handles load failures by showing
 * a styled placeholder instead of the browser's broken-image icon.
 */
export function FallbackImage({
  fallbackIcon,
  fallbackClassName,
  className,
  alt,
  onError: externalOnError,
  ...rest
}: FallbackImageProps) {
  const [failed, setFailed] = useState(false);

  const handleError = useCallback(
    (e: React.SyntheticEvent<HTMLImageElement>) => {
      setFailed(true);
      externalOnError?.(e);
    },
    [externalOnError],
  );

  if (failed) {
    return (
      <div
        className={
          fallbackClassName ??
          "flex h-full w-full items-center justify-center bg-surface-3/60 text-gray-600"
        }
      >
        {fallbackIcon ?? <ImageOff size={24} strokeWidth={1.5} />}
      </div>
    );
  }

  return (
    <img
      className={className}
      alt={alt}
      onError={handleError}
      {...rest}
    />
  );
}
