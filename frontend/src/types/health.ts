export interface HealthStatus {
  status: string;
  app: string;
  version: string;
  environment: string;
  primary_tts_provider: string;
  fallback_tts_enabled: boolean;
  phase_1_status: string;
}
