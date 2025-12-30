import { apiClient } from './client';

export const modelsApi = {
  list: () => apiClient.get<string[]>('/models'),
};
