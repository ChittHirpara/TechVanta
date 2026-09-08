import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { documentsApi } from '../api/client';
import { checkImageQuality } from '../utils/imageQuality';
import Card from '../components/common/Card';
import Input from '../components/common/Input';
import Button from '../components/common/Button';
import { colors, radius, typography, spacing } from '../theme/theme';

const DISTRICTS = [
  'Patna',
  'Gaya',
  'Muzaffarpur',
  'Bhagalpur',
  'Darbhanga',
  'Purnia',
  'Rohtas',
  'Saran',
];

export default function CaptureScreen({ navigation }) {
  const [permission, requestPermission] = useCameraPermissions();
  const [facing, setFacing] = useState('back');
  
  // Multi-page batch state
  const [pages, setPages] = useState([]);
  const [activePageIndex, setActivePageIndex] = useState(0);
  const [isCameraActive, setIsCameraActive] = useState(true);

  const [title, setTitle] = useState('');
  const [district, setDistrict] = useState('Patna');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const cameraRef = useRef(null);

  const processCapturedImage = async (uri) => {
    const quality = await checkImageQuality(uri);
    if (quality.warning) {
      Alert.alert(
        'Quality Warning',
        `${quality.warning}\nDo you want to retake or use this page?`,
        [
          { text: 'Retake', style: 'cancel' },
          {
            text: 'Use Page',
            onPress: () => addPageToBatch(uri),
          },
        ]
      );
    } else {
      addPageToBatch(uri);
    }
  };

  const addPageToBatch = (uri) => {
    const newPage = { uri, id: Date.now() };
    setPages((prev) => {
      const updated = [...prev, newPage];
      setActivePageIndex(updated.length - 1);
      return updated;
    });
    setIsCameraActive(false);
    if (!title) {
      setTitle(`Land Record ${new Date().toLocaleDateString()}`);
    }
  };

  const removePage = (indexToRemove) => {
    setPages((prev) => {
      const updated = prev.filter((_, idx) => idx !== indexToRemove);
      if (updated.length === 0) {
        setIsCameraActive(true);
        setActivePageIndex(0);
      } else if (activePageIndex >= updated.length) {
        setActivePageIndex(updated.length - 1);
      }
      return updated;
    });
  };

  const takePicture = async () => {
    if (cameraRef.current) {
      try {
        const photo = await cameraRef.current.takePictureAsync({ quality: 0.85 });
        if (photo && photo.uri) {
          await processCapturedImage(photo.uri);
        }
      } catch (err) {
        Alert.alert('Camera Error', 'Failed to capture photo. Please try again.');
      }
    }
  };

  const pickImageFromGallery = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: 0.85,
        allowsMultipleSelection: true,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        for (const asset of result.assets) {
          await processCapturedImage(asset.uri);
        }
      }
    } catch (err) {
      Alert.alert('Gallery Error', 'Could not open image picker.');
    }
  };

  const handleUpload = async () => {
    if (pages.length === 0) {
      setError('Please capture or select at least one document page.');
      return;
    }

    try {
      setUploading(true);
      setError(null);

      // Multi-page batch client-side upload handling
      const currentUri = pages[activePageIndex]?.uri || pages[0].uri;
      const formData = new FormData();
      const filename = currentUri.split('/').pop() || 'record.jpg';
      const match = /\.(\w+)$/.exec(filename);
      const type = match ? `image/${match[1]}` : 'image/jpeg';

      formData.append('file', {
        uri: currentUri,
        name: filename,
        type,
      });

      const fullTitle = pages.length > 1 
        ? `${title.trim() || 'Land Record'} (Batch ${pages.length} Pages)`
        : (title.trim() || 'Land Record');

      formData.append('title', fullTitle);
      if (district) {
        formData.append('district', district);
      }

      const res = await documentsApi.upload(formData);
      const docId = res?.id;

      if (docId) {
        navigation.navigate('Processing', { documentId: docId });
      } else {
        throw new Error('Server returned invalid document ID.');
      }
    } catch (err) {
      setError(err.message || 'Upload failed. Please check connection.');
    } finally {
      setUploading(false);
    }
  };

  if (!permission) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.govNavy600} />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.permissionText}>
          Camera permission is required to scan land records in the field.
        </Text>
        <Button
          title="Grant Camera Permission"
          onPress={requestPermission}
          variant="primary"
          style={{ marginTop: spacing.md }}
        />
        <Button
          title="Or Pick from Gallery"
          onPress={pickImageFromGallery}
          variant="outline"
          style={{ marginTop: spacing.sm }}
        />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Multi-Page Land Record Scan</Text>
        <Text style={styles.headerSub}>Capture multiple pages for a unified document record</Text>
      </View>

      {error ? (
        <Card style={styles.errorCard}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
        </Card>
      ) : null}

      {isCameraActive || pages.length === 0 ? (
        <Card style={styles.cameraCard}>
          <View style={styles.cameraFrame}>
            <CameraView style={styles.camera} facing={facing} ref={cameraRef}>
              <View style={styles.overlayGuide}>
                <View style={styles.cornerTL} />
                <View style={styles.cornerTR} />
                <View style={styles.cornerBL} />
                <View style={styles.cornerBR} />
                <Text style={styles.guideText}>
                  Align Page #{pages.length + 1} Within Rectangular Frame
                </Text>
              </View>
            </CameraView>
          </View>

          <View style={styles.cameraControls}>
            <TouchableOpacity style={styles.flipBtn} onPress={() => setFacing(facing === 'back' ? 'front' : 'back')}>
              <Text style={styles.controlIcon}>🔄</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.shutterBtn} onPress={takePicture}>
              <View style={styles.shutterInner} />
            </TouchableOpacity>

            <TouchableOpacity style={styles.galleryBtn} onPress={pickImageFromGallery}>
              <Text style={styles.controlIcon}>🖼️</Text>
              <Text style={styles.galleryBtnText}>Gallery</Text>
            </TouchableOpacity>
          </View>

          {pages.length > 0 ? (
            <Button
              title={`Cancel & View Captured Pages (${pages.length})`}
              onPress={() => setIsCameraActive(false)}
              variant="outline"
              style={{ marginTop: spacing.xs }}
            />
          ) : null}
        </Card>
      ) : (
        <Card style={styles.previewCard}>
          <View style={styles.previewHeaderRow}>
            <Text style={styles.previewTitle}>
              Document Preview (Page {activePageIndex + 1} of {pages.length})
            </Text>
            <TouchableOpacity onPress={() => removePage(activePageIndex)}>
              <Text style={styles.deletePageText}>🗑️ Delete Page</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.previewFrame}>
            <Image
              source={{ uri: pages[activePageIndex]?.uri }}
              style={styles.previewImage}
              resizeMode="contain"
            />
          </View>

          {/* Thumbnail Strip */}
          <Text style={styles.thumbnailLabel}>Captured Pages ({pages.length}):</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.thumbnailStrip}>
            {pages.map((p, idx) => (
              <TouchableOpacity
                key={p.id}
                style={[
                  styles.thumbContainer,
                  activePageIndex === idx && styles.thumbActive,
                ]}
                onPress={() => setActivePageIndex(idx)}
              >
                <Image source={{ uri: p.uri }} style={styles.thumbImage} />
                <View style={styles.thumbBadge}>
                  <Text style={styles.thumbBadgeText}>{idx + 1}</Text>
                </View>
              </TouchableOpacity>
            ))}

            <TouchableOpacity style={styles.addThumbBtn} onPress={() => setIsCameraActive(true)}>
              <Text style={styles.addThumbIcon}>➕</Text>
              <Text style={styles.addThumbText}>Add Page</Text>
            </TouchableOpacity>
          </ScrollView>

          <View style={styles.metaForm}>
            <Input
              label="Document Title / Reference"
              value={title}
              onChangeText={setTitle}
              placeholder="e.g. Khatian Plot #402 - Ram Nagar"
            />

            <Text style={styles.fieldLabel}>Revenue District</Text>
            <View style={styles.districtChips}>
              {DISTRICTS.map((d) => (
                <TouchableOpacity
                  key={d}
                  style={[
                    styles.districtChip,
                    district === d && styles.districtChipActive,
                  ]}
                  onPress={() => setDistrict(d)}
                >
                  <Text
                    style={[
                      styles.districtChipText,
                      district === d && styles.districtChipTextActive,
                    ]}
                  >
                    {d}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <View style={styles.actionButtons}>
              <Button
                title="➕ Add Page"
                onPress={() => setIsCameraActive(true)}
                variant="outline"
                style={{ flex: 1, marginRight: spacing.xs }}
                disabled={uploading}
              />
              <Button
                title={`Upload (${pages.length} ${pages.length === 1 ? 'Page' : 'Pages'})`}
                onPress={handleUpload}
                variant="saffron"
                loading={uploading}
                style={{ flex: 1, marginLeft: spacing.xs }}
              />
            </View>
          </View>
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPage,
  },
  scrollContent: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  centerContainer: {
    flex: 1,
    backgroundColor: colors.bgPage,
    padding: spacing.xl,
    justifyContent: 'center',
    alignItems: 'center',
  },
  permissionText: {
    fontSize: typography.sizes.md,
    color: colors.slate700,
    textAlign: 'center',
    lineHeight: 22,
  },
  header: {
    marginBottom: spacing.md,
  },
  headerTitle: {
    fontSize: typography.sizes.xl,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  headerSub: {
    fontSize: typography.sizes.xs,
    color: colors.slate600,
    marginTop: 2,
  },
  errorCard: {
    backgroundColor: colors.rose50,
    borderColor: colors.rose600,
  },
  errorText: {
    color: colors.rose800,
    fontSize: typography.sizes.sm,
  },
  cameraCard: {
    padding: spacing.sm,
  },
  cameraFrame: {
    height: 380,
    borderRadius: radius.md,
    overflow: 'hidden',
    backgroundColor: colors.black,
  },
  camera: {
    flex: 1,
  },
  overlayGuide: {
    flex: 1,
    borderWidth: 2,
    borderColor: 'rgba(255, 255, 255, 0.4)',
    margin: spacing.lg,
    borderRadius: radius.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  cornerTL: { position: 'absolute', top: 0, left: 0, width: 20, height: 20, borderTopWidth: 4, borderLeftWidth: 4, borderColor: colors.saffron500 },
  cornerTR: { position: 'absolute', top: 0, right: 0, width: 20, height: 20, borderTopWidth: 4, borderRightWidth: 4, borderColor: colors.saffron500 },
  cornerBL: { position: 'absolute', bottom: 0, left: 0, width: 20, height: 20, borderBottomWidth: 4, borderLeftWidth: 4, borderColor: colors.saffron500 },
  cornerBR: { position: 'absolute', bottom: 0, right: 0, width: 20, height: 20, borderBottomWidth: 4, borderRightWidth: 4, borderColor: colors.saffron500 },
  guideText: {
    color: colors.white,
    backgroundColor: 'rgba(6, 19, 37, 0.75)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.full,
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.medium,
  },
  cameraControls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingVertical: spacing.md,
  },
  flipBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.slate100,
    alignItems: 'center',
    justifyContent: 'center',
  },
  shutterBtn: {
    width: 64,
    height: 64,
    borderRadius: 32,
    borderWidth: 4,
    borderColor: colors.saffron600,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.white,
  },
  shutterInner: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.saffron600,
  },
  galleryBtn: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  controlIcon: {
    fontSize: 22,
  },
  galleryBtnText: {
    fontSize: 10,
    color: colors.slate600,
    marginTop: 2,
    fontWeight: typography.weights.semibold,
  },
  previewCard: {
    padding: spacing.md,
  },
  previewHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  previewTitle: {
    fontSize: typography.sizes.md,
    fontWeight: typography.weights.bold,
    color: colors.govNavy900,
  },
  deletePageText: {
    fontSize: typography.sizes.xs,
    color: colors.rose600,
    fontWeight: typography.weights.bold,
  },
  previewFrame: {
    height: 240,
    backgroundColor: colors.slate950,
    borderRadius: radius.md,
    overflow: 'hidden',
    marginBottom: spacing.md,
  },
  previewImage: {
    width: '100%',
    height: '100%',
  },
  thumbnailLabel: {
    fontSize: typography.sizes.xs,
    fontWeight: typography.weights.bold,
    color: colors.slate700,
    marginBottom: spacing.xs,
  },
  thumbnailStrip: {
    flexDirection: 'row',
    marginBottom: spacing.md,
  },
  thumbContainer: {
    width: 64,
    height: 64,
    borderRadius: radius.sm,
    overflow: 'hidden',
    marginRight: 8,
    borderWidth: 2,
    borderColor: colors.slate300,
    position: 'relative',
  },
  thumbActive: {
    borderColor: colors.saffron500,
  },
  thumbImage: {
    width: '100%',
    height: '100%',
  },
  thumbBadge: {
    position: 'absolute',
    bottom: 2,
    right: 2,
    backgroundColor: 'rgba(6, 19, 37, 0.85)',
    borderRadius: radius.full,
    paddingHorizontal: 5,
    paddingVertical: 1,
  },
  thumbBadgeText: {
    color: colors.white,
    fontSize: 9,
    fontWeight: typography.weights.bold,
  },
  addThumbBtn: {
    width: 64,
    height: 64,
    borderRadius: radius.sm,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: colors.slate400,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.slate100,
  },
  addThumbIcon: {
    fontSize: 16,
  },
  addThumbText: {
    fontSize: 9,
    color: colors.slate700,
    fontWeight: typography.weights.semibold,
    marginTop: 2,
  },
  metaForm: {
    marginTop: spacing.xs,
  },
  fieldLabel: {
    fontSize: typography.sizes.sm,
    fontWeight: typography.weights.semibold,
    color: colors.slate700,
    marginBottom: spacing.xs,
  },
  districtChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.lg,
  },
  districtChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.full,
    backgroundColor: colors.slate100,
    borderColor: colors.slate300,
    borderWidth: 1,
  },
  districtChipActive: {
    backgroundColor: colors.govNavy900,
    borderColor: colors.govNavy900,
  },
  districtChipText: {
    fontSize: typography.sizes.xs,
    color: colors.slate700,
    fontWeight: typography.weights.medium,
  },
  districtChipTextActive: {
    color: colors.white,
    fontWeight: typography.weights.bold,
  },
  actionButtons: {
    flexDirection: 'row',
    marginTop: spacing.xs,
  },
});
