<script lang="ts">
	import { onMount } from 'svelte';
	import { BACKEND, humanizeError, humanizeException } from '$lib/http';

	type Status = 'idle' | 'loading' | 'ok' | 'error';

	// captura
	let capStatus: Status = $state('idle');
	let imgUrl: string | null = $state(null);
	let capError = $state('');

	// descrição (VLM)
	let descStatus: Status = $state('idle');
	let description: string | null = $state(null);
	let descLatency = $state(0);
	let descModel = $state('');
	let descError = $state('');

	// health do VLM
	let vlmReady: boolean | null = $state(null);
	let vlmModel = $state('');
	let vlmIssue: string | null = $state(null);
	let issueOpen = $state(false);

	onMount(refreshVlmStatus);

	async function refreshVlmStatus() {
		try {
			const res = await fetch(`${BACKEND}/vlm/status`);
			if (!res.ok) {
				vlmReady = false;
				vlmIssue = `Backend respondeu HTTP ${res.status}`;
				return;
			}
			const body = (await res.json()) as { ready: boolean; model: string; issue: string | null };
			vlmReady = body.ready;
			vlmModel = body.model;
			vlmIssue = body.issue;
		} catch (e) {
			vlmReady = false;
			vlmIssue = `Backend offline: ${humanizeException(e)}`;
		}
	}

	async function capture() {
		capStatus = 'loading';
		capError = '';
		try {
			const res = await fetch(`${BACKEND}/capture`, { method: 'POST' });
			if (!res.ok) {
				capError = humanizeError(res.status, await res.text());
				capStatus = 'error';
				return;
			}
			const blob = await res.blob();
			if (imgUrl) URL.revokeObjectURL(imgUrl);
			imgUrl = URL.createObjectURL(blob);
			capStatus = 'ok';
		} catch (e) {
			capError = humanizeException(e);
			capStatus = 'error';
		}
	}

	async function describe() {
		descStatus = 'loading';
		descError = '';
		try {
			const res = await fetch(`${BACKEND}/describe`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: '{}'
			});
			const text = await res.text();
			if (!res.ok) {
				descError = humanizeError(res.status, text);
				descStatus = 'error';
				refreshVlmStatus();
				return;
			}
			const body = JSON.parse(text) as { description: string; latency_ms: number; model: string };
			description = body.description;
			descLatency = body.latency_ms;
			descModel = body.model;
			descStatus = 'ok';
		} catch (e) {
			descError = humanizeException(e);
			descStatus = 'error';
		}
	}
</script>

<main>
	<header>
		<h1>Inspect</h1>
		<p class="subtitle">Capturar tela e pedir descrição em pt-br (debug do M2).</p>
		{#if vlmReady === null}
			<span class="badge badge-pending">VLM…</span>
		{:else if vlmReady}
			<span class="badge badge-ok">VLM pronto · {vlmModel}</span>
		{:else}
			<button
				type="button"
				class="badge badge-bad"
				onclick={() => (issueOpen = !issueOpen)}
				title="Clique para detalhes"
			>
				VLM indisponível {issueOpen ? '▾' : '▸'}
			</button>
			{#if issueOpen && vlmIssue}
				<p class="issue">{vlmIssue}</p>
			{/if}
		{/if}
	</header>

	<div class="actions">
		<button onclick={capture} disabled={capStatus === 'loading'}>
			{capStatus === 'loading' ? 'Capturando…' : 'Capturar tela'}
		</button>
		<button onclick={describe} disabled={descStatus === 'loading' || vlmReady === false}>
			{descStatus === 'loading' ? 'Pensando…' : 'Descrever tela'}
		</button>
	</div>

	{#if capStatus === 'error'}
		<p class="error">Captura falhou: {capError}</p>
	{/if}

	{#if descStatus === 'error'}
		<p class="error">Descrição falhou: {descError}</p>
	{/if}

	{#if imgUrl}
		<figure>
			<img src={imgUrl} alt="Screenshot capturado pelo sidecar" />
		</figure>
	{/if}

	{#if description}
		<section class="description">
			<h2>Descrição</h2>
			<p>{description}</p>
			<small>latência: {descLatency}ms · {descModel}</small>
		</section>
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

	header {
		margin-bottom: 1.5rem;
	}

	h1 {
		margin: 0 0 0.25rem;
		font-size: 1.75rem;
	}

	h2 {
		margin: 0 0 0.5rem;
		font-size: 1.1rem;
		color: #374151;
	}

	.subtitle {
		margin: 0 0 0.75rem;
		color: #6b7280;
	}

	.badge {
		display: inline-block;
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
		font-size: 0.8rem;
		font-weight: 500;
		border: 1px solid transparent;
		line-height: 1.4;
	}

	.badge-ok {
		background: #ecfdf5;
		color: #065f46;
		border-color: #6ee7b7;
	}

	.badge-bad {
		background: #fef2f2;
		color: #991b1b;
		border-color: #fca5a5;
		cursor: pointer;
		font: inherit;
		font-size: 0.8rem;
		font-weight: 500;
	}

	.badge-pending {
		background: #f3f4f6;
		color: #6b7280;
		border-color: #d1d5db;
	}

	.issue {
		margin: 0.5rem 0 0;
		padding: 0.5rem 0.75rem;
		background: #fef2f2;
		border: 1px solid #fecaca;
		border-radius: 6px;
		color: #7f1d1d;
		font-size: 0.85rem;
		white-space: pre-wrap;
	}

	.actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
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
		cursor: not-allowed;
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

	.description {
		margin-top: 1.5rem;
		padding: 1rem 1.25rem;
		background: #f9fafb;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
	}

	.description p {
		margin: 0 0 0.5rem;
		white-space: pre-wrap;
		line-height: 1.5;
	}

	.description small {
		color: #6b7280;
		font-size: 0.75rem;
	}
</style>
