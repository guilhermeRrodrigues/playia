/**
 * Utilitários compartilhados de HTTP entre as rotas que falam com o
 * sidecar Python. Mantém a URL base num só lugar e centraliza a
 * tradução de erros do FastAPI para frases acionáveis em pt-br.
 */

export const BACKEND = 'http://127.0.0.1:8765';

/**
 * Traduz um erro HTTP do sidecar para uma mensagem pt-br que o usuário
 * consiga acionar. Aceita o status code + o corpo bruto (geralmente o
 * `{"detail": "..."}` do FastAPI).
 */
export function humanizeError(status: number, text: string): string {
	if (status === 503) return 'Ollama não está rodando. Rode `ollama serve` em outro terminal.';
	if (status === 404) return 'Modelo VLM não baixado. Rode `ollama pull qwen2.5vl:3b`.';
	if (status === 504) return 'A IA demorou demais para responder (>60s). Tente de novo.';
	try {
		const j = JSON.parse(text);
		if (j?.detail) return String(j.detail);
	} catch {
		// noop
	}
	return `HTTP ${status}: ${text}`;
}

/** Encoder de erro genérico (catch fora do try HTTP). */
export function humanizeException(e: unknown): string {
	return e instanceof Error ? e.message : String(e);
}
