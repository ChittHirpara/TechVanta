import 'react-native-gesture-handler';
import { registerRootComponent } from 'expo';
import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider } from './src/context/AuthContext';
import AppNavigator from './src/navigation/AppNavigator';

function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <StatusBar style="light" backgroundColor="#0b1f3a" />
        <AppNavigator />
      </AuthProvider>
    </SafeAreaProvider>
  );
}

registerRootComponent(App);
