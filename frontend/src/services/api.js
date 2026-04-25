import axios from 'axios';

const client = axios.create({ timeout: 10000 });

export async function getDataStatus() {
  const url = import.meta.env.REACT_APP_DATA_STATUS_URL || '/api/status';
  const response = await client.get(url, { responseType: 'json' });
  return response.data;
}
