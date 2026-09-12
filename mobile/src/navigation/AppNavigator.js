import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { NavigationContainer } from '@react-navigation/native';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { useAuth } from '../context/AuthContext';

import GovHeader from '../components/common/GovHeader';
import LoginScreen from '../screens/LoginScreen';
import MainTabs from './MainTabs';
import ReviewScreen from '../screens/ReviewScreen';
import ProcessingScreen from '../screens/ProcessingScreen';
import { colors } from '../theme/theme';

const Stack = createNativeStackNavigator();

export default function AppNavigator() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.saffron500} />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName={isAuthenticated ? 'Main' : 'Login'}
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.govNavy950 },
        }}
      >
        {!isAuthenticated ? (
          <Stack.Screen
            name="Login"
            component={LoginScreen}
          />
        ) : (
          <>
            <Stack.Screen
              name="Main"
              component={MainTabs}
            />
            <Stack.Screen
              name="Review"
              component={ReviewScreen}
              options={{
                headerShown: true,
                header: () => <GovHeader title="Deed Verification & Audit" showBack={true} />,
              }}
            />
            <Stack.Screen
              name="Processing"
              component={ProcessingScreen}
              options={{
                headerShown: true,
                header: () => <GovHeader title="Real-time Pipeline Stream" showBack={true} />,
              }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: colors.govNavy950,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
