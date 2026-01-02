import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../contexts/AuthContext";
import InventoryOverviewPage from "./InventoryOverviewPage";
import InventoryItemDetailPage from "./InventoryItemDetailPage";

export const InventoryApp: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter basename="/inventory">
        <Routes>
          <Route path="/" element={<InventoryOverviewPage />} />
          <Route path="/items/:itemId" element={<InventoryItemDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default InventoryApp;

