import axios from 'axios';

// All API calls go through this base URL
const BASE = 'http://localhost:8080/api';

export const fetchMetrics      = () => axios.get(`${BASE}/metrics`);
export const fetchAlerts       = () => axios.get(`${BASE}/alerts`);
export const fetchFunnel       = () => axios.get(`${BASE}/funnel`);
export const fetchHourly       = () => axios.get(`${BASE}/analytics/hourly`);
export const fetchZones        = () => axios.get(`${BASE}/analytics/zones`);
export const fetchEvents       = () => axios.get(`${BASE}/events`);