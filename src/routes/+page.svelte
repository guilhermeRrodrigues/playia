<script lang="ts">
	type Status = 'idle' | 'loading' | 'ok' | 'error';

	let status: Status = $state('idle');
	let imgUrl: string | null = $state(null);
	let errorMsg = $state('');

	async function capture() {
		status = 'loading';
		errorMsg = '';
		try {
			const res = await fetch('http://127.0.0.1:8765/capture', { method: 'POST' });
			if (!res.ok) {
				errorMsg = `HTTP ${res.status}: ${await res.text()}`;
				status = 'error';
				return;
			}
			const blob = await res.blob();
			if (imgUrl) URL.revokeObjectURL(imgUrl);
			imgUrl = URL.createObjectURL(blob);
			status = 'ok';
		} catch (e) {
			errorMsg = e instanceof Error ? e.message : String(e);
			status = 'error';
		}
	}
</script>

<main>
	<h1>PlayIA — M1</h1>
	<p class="subtitle">Hello world arquitetural: Tauri ↔ Python ↔ captura de tela.</p>

	<button onclick={capture} disabled={status === 'loading'}>
		{status === 'loading' ? 'Capturando…' : 'Capturar tela'}
	</button>

	{#if status === 'error'}
		<p class="error">Falhou: {errorMsg}</p>
	{/if}

	{#if imgUrl}
		<figure>
			<img src={imgUrl} alt="Screenshot capturado pelo sidecar" />
		</figure>
	{/if}
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

	h1 {
		margin: 0 0 0.25rem;
		font-size: 1.75rem;
	}

	.subtitle {
		margin: 0 0 1.5rem;
		color: #6b7280;
	}

	button {
		font-size: 1rem;
		padding: 0.6rem 1.1rem;
		border: 1px solid #1f2937;
		border-radius: 6px;
		background: #1f2937;
		color: white;
		cursor: pointer;
		transition: background 120ms ease;
	}

	button:hover:not(:disabled) {
		background: #374151;
	}

	button:disabled {
		opacity: 0.6;
		cursor: progress;
	}

	.error {
		margin-top: 1rem;
		padding: 0.75rem 1rem;
		background: #fee2e2;
		border: 1px solid #fca5a5;
		border-radius: 6px;
		color: #991b1b;
		white-space: pre-wrap;
	}

	figure {
		margin: 1.5rem 0 0;
	}

	img {
		max-width: 100%;
		height: auto;
		border: 1px solid #d1d5db;
		border-radius: 6px;
	}
</style>
