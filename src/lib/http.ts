/**
 * Utilitários compartilhados de HTTP entre as rotas que falam com o
 * sidecar Python. Mantém a URL base num só lugar e centraliza a
 * tradução de erros do FastAPI para frases acionáveis em pt-br.
 */

export const BACKEND = 'http://127.0.0.1:8765';

/**
 * Traduz um erro HTTP do sidecar para uma mensagem pt-br que o usuário
 * consiga acionar.
 *
 * Estratégia: primeiro tenta extrair o `detail` do FastAPI — o backend
 * já formata mensagens específicas em pt-br por endpoint (ex.: "jogo
 * desconhecido", "nenhum motor_model treinado…"). Só se o body não tiver
 * detail útil é que caímos pra heurística por status code (503/504, que
 * o backend nem sempre detalha em /describe quando a rede falha).
 *
 * Importante: NÃO mapeie 404 globalmente para "VLM ausente" — qualquer
 * endpoint do app pode devolver 404 com significado próprio
 * (/games/{id}, /recordings/{id}, /motor-models/{id}). O backend já
 * carrega o detail certo.
 */
export function humanizeError(status: number, text: string): string {
	try {
		const j = JSON.parse(text);
		if (j?.detail) return String(j.detail);
	} catch {
		// body não é JSON — segue pra heurística.
	}
	if (status === 503) return 'Ollama não está rodando. Rode `ollama serve` em outro terminal.';
	if (status === 504) return 'A IA demorou demais para responder (>60s). Tente de novo.';
	return `HTTP ${status}: ${text}`;
}

/** Encoder de erro genérico (catch fora do try HTTP). */
export function humanizeException(e: unknown): string {
	return e instanceof Error ? e.message : String(e);
}
