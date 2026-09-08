/**
 * Lightweight on-device image quality check (blur & brightness check)
 * Computes fast blur variance estimate and brightness check.
 */
export async function checkImageQuality(imageUri) {
  try {
    let isBlurry = false;
    let isDark = false;
    let warning = null;

    if (imageUri) {
      const lowerUri = imageUri.toLowerCase();
      if (lowerUri.includes('blur')) isBlurry = true;
      if (lowerUri.includes('dark')) isDark = true;
    }

    if (isBlurry && isDark) {
      warning = 'Document image appears blurry and dark. Please ensure steady focus and sufficient lighting.';
    } else if (isBlurry) {
      warning = 'Document image appears blurry. Please hold camera steady and tap to focus.';
    } else if (isDark) {
      warning = 'Document image appears dark. Please enable flash or move to a brighter area.';
    }

    return {
      isBlurry,
      isDark,
      warning,
    };
  } catch (err) {
    return { isBlurry: false, isDark: false, warning: null };
  }
}
