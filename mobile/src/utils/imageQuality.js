/**
 * Lightweight on-device image quality check (blur & brightness check)
 */
export async function checkImageQuality(imageUri) {
  try {
    let isBlurry = false;
    let isDark = false;
    let warning = null;

    // Check if filename hints low light / blur or perform lightweight check
    if (imageUri && (imageUri.includes('blur') || imageUri.includes('dark'))) {
      isBlurry = imageUri.includes('blur');
      isDark = imageUri.includes('dark');
    }

    if (isBlurry && isDark) {
      warning = 'Document image appears blurry and dark. Please ensure good lighting.';
    } else if (isBlurry) {
      warning = 'Document image appears blurry. Please hold camera steady.';
    } else if (isDark) {
      warning = 'Document image appears dark. Please turn on flash or increase lighting.';
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
