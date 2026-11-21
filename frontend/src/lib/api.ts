import importAxios from "axios";

const getApiBaseUrl = () => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== "undefined") {
    const hostname = window.location.hostname;
    return `http://${hostname}:8000/api`;
  }
  return "http://127.0.0.1:8000/api";
};

const API_BASE_URL = getApiBaseUrl();

export const api = importAxios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: any) => void;
  reject: (reason?: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 429 Rate Limiting with user-friendly alert
    if (error.response?.status === 429) {
      const waitMsg = "Too many requests. Please wait a moment before trying again (API Rate Limit reached).";
      if (typeof window !== "undefined") {
        console.warn("JanSahayak Rate Limit Warning:", waitMsg);
      }
      return Promise.reject(new Error(waitMsg));
    }

    // Handle 401 Unauthorized with automatic JWT Token Refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (typeof window !== "undefined" && originalRequest.url?.includes("/auth/login/")) {
        return Promise.reject(error);
      }

      if (typeof window !== "undefined" && originalRequest.url?.includes("/auth/refresh/")) {
        localStorage.removeItem("token");
        localStorage.removeItem("refreshToken");
        localStorage.removeItem("user");
        if (!window.location.pathname.includes("/login")) {
          window.location.assign("/login");
        }
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise(function (resolve, reject) {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers["Authorization"] = "Bearer " + token;
            return api(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = typeof window !== "undefined" ? localStorage.getItem("refreshToken") : null;

      if (!refreshToken) {
        isRefreshing = false;
        if (typeof window !== "undefined" && !window.location.pathname.includes("/login")) {
          localStorage.removeItem("token");
          localStorage.removeItem("user");
          window.location.assign("/login");
        }
        return Promise.reject(error);
      }

      try {
        const refreshResponse = await importAxios.post(`${API_BASE_URL}/auth/refresh/`, {
          refresh: refreshToken,
        });

        const newAccessToken = refreshResponse.data.access;
        localStorage.setItem("token", newAccessToken);
        if (refreshResponse.data.refresh) {
          localStorage.setItem("refreshToken", refreshResponse.data.refresh);
        }

        api.defaults.headers.common["Authorization"] = `Bearer ${newAccessToken}`;
        originalRequest.headers["Authorization"] = `Bearer ${newAccessToken}`;

        processQueue(null, newAccessToken);
        return api(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        if (typeof window !== "undefined") {
          localStorage.removeItem("token");
          localStorage.removeItem("refreshToken");
          localStorage.removeItem("user");
          if (!window.location.pathname.includes("/login")) {
            window.location.assign("/login");
          }
        }
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
