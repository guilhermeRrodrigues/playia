<script lang="ts">
	// Home: 2 cards apontando para os modos do app.
</script>

<main>
	<header>
		<h1>PlayIA</h1>
		<p class="subtitle">A IA enxerga sua tela, descreve e (no /play) joga sozinha.</p>
	</header>

	<div class="cards">
		<a class="card play" href="/play">
			<h2>Play</h2>
			<p>Loop fechado: a IA vê a tela e joga sozinha um jogo simples (2048 no M3).</p>
			<span class="cta">Iniciar →</span>
		</a>
		<a class="card games" href="/games">
			<h2>Jogos</h2>
			<p>Catálogo persistente. Tempo (turn-based / realtime) e flag de anti-cheat.</p>
			<span class="cta">Abrir →</span>
		</a>
		<a class="card inspect" href="/inspect">
			<h2>Inspect</h2>
			<p>Capturar tela e pedir descrição em pt-br. Útil para debugar o VLM.</p>
			<span class="cta">Abrir →</span>
		</a>
	</div>

	<footer>
		<small>M4 — memória SQLite persistente. Próximo: gravação de sessões (M5).</small>
	</footer>
</main>

<style>
	main {
		max-width: 960px;
		margin: 0 auto;
		padding: 2rem 1.5rem;
		font-family:
			ui-sans-serif,
			system-ui,
			-apple-system,
			'Segoe UI',
			sans-serif;
		color: #1f2937;
	}

	header {
		margin-bottom: 2rem;
	}

	h1 {
		margin: 0 0 0.25rem;
		font-size: 2rem;
	}

	h2 {
		margin: 0 0 0.5rem;
		font-size: 1.25rem;
		color: #1f2937;
	}

	.subtitle {
		margin: 0;
		color: #6b7280;
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 1rem;
	}

	@media (max-width: 900px) {
		.cards {
			grid-template-columns: 1fr 1fr;
		}
	}

	@media (max-width: 640px) {
		.cards {
			grid-template-columns: 1fr;
		}
	}

	.card {
		display: block;
		padding: 1.5rem 1.25rem;
		background: #f9fafb;
		border: 1px solid #e5e7eb;
		border-radius: 10px;
		text-decoration: none;
		color: inherit;
		transition:
			transform 120ms ease,
			border-color 120ms ease,
			background 120ms ease;
	}

	.card:hover {
		transform: translateY(-2px);
		border-color: #1f2937;
		background: #fff;
	}

	.card.play h2 {
		color: #047857;
	}

	.card.games h2 {
		color: #b45309;
	}

	.card.inspect h2 {
		color: #1d4ed8;
	}

	.card p {
		margin: 0 0 0.75rem;
		color: #4b5563;
		line-height: 1.4;
	}

	.cta {
		font-weight: 600;
		color: #1f2937;
	}

	footer {
		margin-top: 2rem;
		color: #9ca3af;
	}
</style>
