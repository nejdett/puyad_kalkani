import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 300000, // 5 dakika
});

// Tüm sistemi tara
export const scanSystem = () => api.get("/scan");

// Tek bir kuralı tara
export const scanSingleRule = (ruleId) => api.get(`/scan/${ruleId}`);

// Belirli bir kuralı düzelt
export const fixRule = (ruleId) => api.post(`/fix/${ruleId}`);

// Belirli bir kuralı görmezden gel
export const ignoreRule = (ruleId) => api.post(`/ignore/${ruleId}`);

// Görmezden gelmeyi kaldır
export const unignoreRule = (ruleId) => api.delete(`/ignore/${ruleId}`);

// Görmezden gelinen kuralları getir
export const getIgnored = () => api.get("/ignored");

// Tüm kuralları getir
export const getRules = () => api.get("/rules");

// Yeni kural ekle
export const addRule = (rule) => api.post("/rules", rule);

// Kural güncelle
export const updateRule = (ruleId, rule) => api.put(`/rules/${ruleId}`, rule);

// Kural sil
export const deleteRule = (ruleId) => api.delete(`/rules/${ruleId}`);

// api objesini export et
export { api };
