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
import * as Location from 'expo-location';
import { Ionicons } from '@expo/vector-icons';
import { checkImageQuality } from '../utils/imageQuality';
import { addToQueue } from '../utils/queueDatabase';
import { syncPendingQueue } from '../services/syncEngine';
import { useI18n } from '../i18n/i18n';
import Card from '../components/common/Card';
import Input from '../components/common/Input';
import Button from '../components/common/Button';
import { colors, radius, typography, spacing, shadows } from '../theme/theme';

export default function CaptureScreen({ navigation }) {
  const { t } = useI18n();
  const [permission, requestPermission] = useCameraPermissions();
  const [facing, setFacing] = useState('back');

  // Multi-page batch state
  const [pages, setPages] = useState([]);
  const [activePageIndex, setActivePageIndex] = useState(0);
  const [isCameraActive, setIsCameraActive] = useState(true);

  const [title, setTitle] = useState('');
  const [district, setDistrict] = useState('Jaipur');
  const [tehsil, setTehsil] = useState('Sanganer');
  const [village, setVillage] = useState('Rampur Kalan');
  const [locating, setLocating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const cameraRef = useRef(null);

  const handleUseLocation = async () => {
    try {
      setLocating(true);
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Permission to access GPS location was denied.');
        return;
      }
      const loc = await Location.getCurrentPositionAsync({});
      if (loc && loc.coords) {
        const [geocode] = await Location.reverseGeocodeAsync({
          latitude: loc.coords.latitude,
          longitude: loc.coords.longitude,
        });
        if (geocode) {
          if (geocode.district || geocode.city || geocode.subregion) {
            setDistrict(geocode.district || geocode.city || geocode.subregion || '');
          }
          if (geocode.subregion || geocode.city) {
            setTehsil(geocode.subregion || geocode.city || '');
          }
          if (geocode.name || geocode.street) {
            setVillage(geocode.name || geocode.street || '');
          }
        }
      }
    } catch (err) {
      Alert.alert('Location Auto-Detect', 'Defaulting to current revenue circle.');
    } finally {
      setLocating(false);
    }
  };

  const processCapturedImage = async (uri) => {
    const quality = await checkImageQuality(uri);
    if (quality.warning) {
      Alert.alert(
        'Quality Advisory',
        `${quality.warning}\nDo you want to retake or proceed with this page?`,
        [
          { text: 'Retake', style: 'cancel' },
          {
            text: 'Proceed Anyway',
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
      setTitle(`Khasra Deed ${new Date().toLocaleDateString()}`);
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
        mediaTypes: ['images'],
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

      // Save to SQLite queue
      const item = await addToQueue({
        title: title.trim() || 'Land Record',
        district,
        tehsil: tehsil.trim(),
        village: village.trim(),
        pages,
      });

      // Trigger sync in background
      syncPendingQueue();

      Alert.alert(
        'Land Deed Ingested Successfully',
        `Queue Reference: ${item.id}\n${pages.length} page(s) queued for AI OCR & sovereign extraction.`,
        [
          {
            text: 'View Queue',
            onPress: () => navigation.navigate('Queue'),
          },
          {
            text: 'Go to Registry',
            onPress: () => navigation.navigate('Registry'),
          },
        ]
      );
    } catch (err) {
      setError(err.message || 'Failed to enqueue capture.');
    } finally {
      setUploading(false);
    }
  };

  if (!permission) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.saffron500} />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.centerContainer}>
        <Ionicons name="camera-outline" size={56} color={colors.saffron500} />
        <Text style={styles.permissionTitle}>Camera Permission Required</Text>
        <Text style={styles.permissionText}>
          BhoomiScan AI needs camera access to scan land deeds and Jamabandi records in the field.
        </Text>
        <Button
          title="Grant Camera Access"
          onPress={requestPermission}
          variant="saffron"
          style={{ marginTop: spacing.md, width: '80%' }}
        />
        <Button
          title="Pick Document from Gallery"
          onPress={pickImageFromGallery}
          variant="outline"
          style={{ marginTop: spacing.sm, width: '80%' }}
        />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
      {/* Screen Title */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Land Record Scanner</Text>
        <Text style={styles.headerSub}>Capture high-resolution deeds with spatial OCR alignment</Text>
      </View>

      {error ? (
        <Card style={styles.errorCard}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name="alert-circle" size={16} color={colors.rose600} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        </Card>
      ) : null}

      {isCameraActive || pages.length === 0 ? (
        <Card style={styles.cameraCard}>
          <View style={styles.cameraFrame}>
            <CameraView style={styles.camera} facing={facing} ref={cameraRef} />
            <View style={styles.overlayGuide} pointerEvents="none">
              <View style={styles.cornerTL} />
              <View style={styles.cornerTR} />
              <View style={styles.cornerBL} />
              <View style={styles.cornerBR} />
              <View style={styles.guideBadge}>
                <Text style={styles.guideText}>
                  Align Page #{pages.length + 1} Inside Cadastral Frame
                </Text>
              </View>
            </View>
          </View>

          {/* Camera Action Controls */}
          <View style={styles.cameraControls}>
            <TouchableOpacity style={styles.controlCircleBtn} onPress={() => setFacing(facing === 'back' ? 'front' : 'back')}>
              <Ionicons name="camera-reverse-outline" size={22} color={colors.white} />
            </TouchableOpacity>

            <TouchableOpacity style={styles.shutterBtn} onPress={takePicture} activeOpacity={0.85}>
              <View style={styles.shutterInner} />
            </TouchableOpacity>

            <TouchableOpacity style={styles.controlCircleBtn} onPress={pickImageFromGallery}>
              <Ionicons name="images-outline" size={22} color={colors.white} />
            </TouchableOpacity>
          </View>

          {pages.length > 0 ? (
            <Button
              title={`View Captured Pages (${pages.length})`}
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
              Page {activePageIndex + 1} of {pages.length}
            </Text>
            <TouchableOpacity
              style={styles.deleteBtn}
              onPress={() => removePage(activePageIndex)}
            >
              <Ionicons name="trash-outline" size={14} color={colors.rose600} />
              <Text style={styles.deletePageText}>Delete Page</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.previewFrame}>
            <Image
              source={{ uri: pages[activePageIndex]?.uri }}
              style={styles.previewImage}
              resizeMode="contain"
            />
          </View>

          {/* Multi-page Thumbnail Strip */}
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
              <Ionicons name="add" size={20} color={colors.govNavy700} />
              <Text style={styles.addThumbText}>Add Page</Text>
            </TouchableOpacity>
          </ScrollView>

          {/* Metadata Form */}
          <View style={styles.metaForm}>
            <View style={styles.locationHeaderRow}>
              <Text style={styles.fieldLabel}>CADASTRAL LOCATION METADATA</Text>
              <TouchableOpacity
                style={styles.gpsBtn}
                onPress={handleUseLocation}
                disabled={locating}
              >
                {locating ? (
                  <ActivityIndicator size="small" color={colors.saffron600} />
                ) : (
                  <>
                    <Ionicons name="navigate-outline" size={12} color={colors.govNavy600} />
                    <Text style={styles.gpsBtnText}>Use GPS</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>

            <Input
              label="Document Title / Registry Ref"
              value={title}
              onChangeText={setTitle}
              placeholder="e.g. Jamabandi Deed #451 - Rampur"
            />

            <View style={styles.locRow}>
              <View style={{ flex: 1, marginRight: spacing.xs }}>
                <Input
                  label="Tehsil / Sub-district"
                  value={tehsil}
                  onChangeText={setTehsil}
                  placeholder="e.g. Sanganer"
                />
              </View>
              <View style={{ flex: 1, marginLeft: spacing.xs }}>
                <Input
                  label="Village / Mauza"
                  value={village}
                  onChangeText={setVillage}
                  placeholder="e.g. Rampur Kalan"
                />
              </View>
            </View>

            <Input
              label="District / Revenue Circle"
              value={district}
              onChangeText={setDistrict}
              placeholder="e.g. Jaipur"
            />

            <View style={styles.actionButtons}>
              <Button
                title="➕ Add Page"
                onPress={() => setIsCameraActive(true)}
                variant="outline"
                style={{ flex: 1, marginRight: spacing.xs }}
                disabled={uploading}
              />
              <Button
                title={uploading ? "Ingesting..." : `Upload Deed (${pages.length} Pages)`}
                onPress={handleUpload}
                variant="saffron"
                loading={uploading}
                style={{ flex: 1.5, marginLeft: spacing.xs }}
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
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  permissionTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.govNavy950,
    marginTop: 12,
  },
  permissionText: {
    fontSize: 13,
    color: colors.slate600,
    textAlign: 'center',
    marginTop: 6,
    lineHeight: 18,
  },
  header: {
    marginBottom: spacing.md,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  headerSub: {
    fontSize: 11,
    color: colors.slate500,
    marginTop: 2,
  },
  errorCard: {
    backgroundColor: colors.rose50,
    borderColor: colors.rose600,
    marginBottom: spacing.md,
  },
  errorText: {
    color: colors.rose800,
    fontSize: 12,
  },
  cameraCard: {
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.sm,
    borderColor: colors.borderCard,
    borderWidth: 1,
    ...shadows.sm,
  },
  cameraFrame: {
    height: 380,
    borderRadius: radius.md,
    overflow: 'hidden',
    backgroundColor: colors.govNavy950,
  },
  camera: {
    flex: 1,
  },
  overlayGuide: {
    position: 'absolute',
    top: 20,
    bottom: 20,
    left: 20,
    right: 20,
    borderWidth: 1.5,
    borderColor: 'rgba(245, 158, 11, 0.6)',
    borderRadius: radius.sm,
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingBottom: 16,
  },
  cornerTL: {
    position: 'absolute',
    top: -2,
    left: -2,
    width: 24,
    height: 24,
    borderTopWidth: 4,
    borderLeftWidth: 4,
    borderColor: colors.saffron500,
  },
  cornerTR: {
    position: 'absolute',
    top: -2,
    right: -2,
    width: 24,
    height: 24,
    borderTopWidth: 4,
    borderRightWidth: 4,
    borderColor: colors.saffron500,
  },
  cornerBL: {
    position: 'absolute',
    bottom: -2,
    left: -2,
    width: 24,
    height: 24,
    borderBottomWidth: 4,
    borderLeftWidth: 4,
    borderColor: colors.saffron500,
  },
  cornerBR: {
    position: 'absolute',
    bottom: -2,
    right: -2,
    width: 24,
    height: 24,
    borderBottomWidth: 4,
    borderRightWidth: 4,
    borderColor: colors.saffron500,
  },
  guideBadge: {
    backgroundColor: 'rgba(6, 19, 37, 0.85)',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },
  guideText: {
    color: colors.white,
    fontSize: 10,
    fontWeight: '700',
  },
  cameraControls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingVertical: 14,
    backgroundColor: colors.govNavy950,
    borderRadius: radius.md,
    marginTop: spacing.sm,
  },
  controlCircleBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255, 255, 255, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  shutterBtn: {
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: 'rgba(255, 255, 255, 0.3)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: colors.saffron500,
  },
  shutterInner: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.white,
  },
  previewCard: {
    backgroundColor: colors.white,
    borderRadius: radius.md,
    padding: spacing.md,
    borderColor: colors.borderCard,
    borderWidth: 1,
    ...shadows.sm,
  },
  previewHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  previewTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.govNavy950,
  },
  deleteBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.rose50,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radius.xs,
  },
  deletePageText: {
    fontSize: 11,
    color: colors.rose700,
    fontWeight: '700',
  },
  previewFrame: {
    height: 260,
    backgroundColor: colors.govNavy950,
    borderRadius: radius.sm,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  previewImage: {
    width: '100%',
    height: '100%',
  },
  thumbnailLabel: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.slate500,
    marginTop: spacing.sm,
    marginBottom: 6,
    letterSpacing: 0.5,
  },
  thumbnailStrip: {
    flexDirection: 'row',
    marginBottom: spacing.md,
  },
  thumbContainer: {
    width: 56,
    height: 72,
    borderRadius: radius.xs,
    overflow: 'hidden',
    marginRight: 8,
    borderWidth: 1,
    borderColor: colors.slate200,
    position: 'relative',
  },
  thumbActive: {
    borderColor: colors.saffron500,
    borderWidth: 2,
  },
  thumbImage: {
    width: '100%',
    height: '100%',
  },
  thumbBadge: {
    position: 'absolute',
    bottom: 2,
    right: 2,
    backgroundColor: colors.govNavy900,
    borderRadius: 8,
    width: 16,
    height: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  thumbBadgeText: {
    color: colors.white,
    fontSize: 9,
    fontWeight: '800',
  },
  addThumbBtn: {
    width: 56,
    height: 72,
    borderRadius: radius.xs,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: colors.slate300,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.slate50,
  },
  addThumbText: {
    fontSize: 8.5,
    color: colors.govNavy700,
    fontWeight: '700',
    marginTop: 2,
  },
  metaForm: {
    marginTop: spacing.xs,
  },
  locationHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  fieldLabel: {
    fontSize: 9.5,
    fontWeight: '800',
    color: colors.slate500,
    letterSpacing: 0.5,
  },
  gpsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.govNavy50,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.govNavy100,
  },
  gpsBtnText: {
    fontSize: 10,
    color: colors.govNavy700,
    fontWeight: '700',
  },
  locRow: {
    flexDirection: 'row',
  },
  actionButtons: {
    flexDirection: 'row',
    marginTop: spacing.md,
  },
});
