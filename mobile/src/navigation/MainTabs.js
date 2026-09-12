import React, { useEffect, useState } from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, typography } from '../theme/theme';
import { getQueuedCount } from '../utils/queueDatabase';

import RegistryScreen from '../screens/RegistryScreen';
import CaptureScreen from '../screens/CaptureScreen';
import QueueScreen from '../screens/QueueScreen';
import AuditScreen from '../screens/AuditScreen';
import ProfileScreen from '../screens/ProfileScreen';
import GovHeader from '../components/common/GovHeader';

const Tab = createBottomTabNavigator();

export default function MainTabs() {
  const [queuedCount, setQueuedCount] = useState(0);

  useEffect(() => {
    async function loadCount() {
      try {
        const count = await getQueuedCount();
        setQueuedCount(count);
      } catch (_) {}
    }
    loadCount();
    const interval = setInterval(loadCount, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Tab.Navigator
      screenOptions={{
        header: () => <GovHeader />,
        tabBarStyle: styles.tabBar,
        tabBarActiveTintColor: colors.saffron500,
        tabBarInactiveTintColor: colors.slate400,
        tabBarLabelStyle: styles.tabLabel,
        tabBarHideOnKeyboard: true,
      }}
    >
      <Tab.Screen
        name="Registry"
        component={RegistryScreen}
        options={{
          tabBarLabel: 'Dashboard',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons
              name={focused ? 'grid' : 'grid-outline'}
              size={22}
              color={color}
            />
          ),
        }}
      />

      <Tab.Screen
        name="Capture"
        component={CaptureScreen}
        options={{
          tabBarLabel: 'Scan Deed',
          tabBarIcon: ({ color, focused }) => (
            <View style={[styles.scanIconWrapper, focused && styles.scanIconWrapperActive]}>
              <Ionicons
                name={focused ? 'scan' : 'scan-outline'}
                size={22}
                color={focused ? colors.govNavy950 : colors.white}
              />
            </View>
          ),
        }}
      />

      <Tab.Screen
        name="Queue"
        component={QueueScreen}
        options={{
          tabBarLabel: 'Offline Queue',
          tabBarBadge: queuedCount > 0 ? queuedCount : undefined,
          tabBarBadgeStyle: styles.queueBadge,
          tabBarIcon: ({ color, focused }) => (
            <Ionicons
              name={focused ? 'cloud-upload' : 'cloud-upload-outline'}
              size={22}
              color={color}
            />
          ),
        }}
      />

      <Tab.Screen
        name="Audit"
        component={AuditScreen}
        options={{
          tabBarLabel: 'Legal Audit',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons
              name={focused ? 'shield-checkmark' : 'shield-checkmark-outline'}
              size={22}
              color={color}
            />
          ),
        }}
      />

      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{
          tabBarLabel: 'Settings',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons
              name={focused ? 'person-circle' : 'person-circle-outline'}
              size={22}
              color={color}
            />
          ),
        }}
      />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: colors.govNavy950,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.08)',
    height: Platform.OS === 'ios' ? 84 : 64,
    paddingTop: 6,
    paddingBottom: Platform.OS === 'ios' ? 24 : 8,
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -3 },
    shadowOpacity: 0.15,
    shadowRadius: 6,
  },
  tabLabel: {
    fontSize: 10,
    fontWeight: '700',
    marginTop: 2,
  },
  scanIconWrapper: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.govNavy700,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: colors.saffron500,
  },
  scanIconWrapperActive: {
    backgroundColor: colors.saffron500,
    borderColor: colors.white,
  },
  queueBadge: {
    backgroundColor: colors.rose600,
    color: colors.white,
    fontSize: 10,
    fontWeight: '800',
  },
});
