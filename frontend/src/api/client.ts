import axios from 'axios'

export const apiClient = axios.create({
  baseURL: '/api',
  withCredentials: false,
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
