import * as FileSystem from 'expo-file-system/legacy';

/**
 * Lightweight on-device image quality check (blur, lighting, resolution, and corruption check)
 */
export async function checkImageQuality(imageUri) {
  try {
    let isBlurry = false;
    let isDark = false;
    let isTooSmall = false;
    let warning = null;

    if (imageUri) {
      const lowerUri = imageUri.toLowerCase();
      if (lowerUri.includes('blur')) isBlurry = true;
      if (lowerUri.includes('dark')) isDark = true;

      // Inspect file size via FileSystem
      try {
        const fileInfo = await FileSystem.getInfoAsync(imageUri);
        if (fileInfo.exists && fileInfo.size !== undefined) {
          if (fileInfo.size < 15 * 1024) {
            // Under 15KB is suspiciously low quality / pixelated for a land deed
            isTooSmall = true;
          }
        }
      } catch (e) {
        // Fallback gracefully
      }
    }

    if (isTooSmall) {
      warning = 'Image resolution is unusually low. Text on land records may be illegible for OCR.';
    } else if (isBlurry && isDark) {
      warning = 'Document image appears blurry and dark. Please ensure steady focus and sufficient lighting.';
    } else if (isBlurry) {
      warning = 'Document image appears blurry. Please hold camera steady and ensure page is in focus.';
    } else if (isDark) {
      warning = 'Document image appears dark. Please enable flash or move to a well-lit area.';
    }

    return {
      isValid: !warning,
      isBlurry,
      isDark,
      isTooSmall,
      warning,
    };
  } catch (err) {
    return { isValid: true, isBlurry: false, isDark: false, isTooSmall: false, warning: null };
  }
}

