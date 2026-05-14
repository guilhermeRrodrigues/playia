<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { BACKEND, humanizeError, humanizeException } from '$lib/http';

	type Game = {
		id: string;
		name: string;
		tempo: string;
		allowed_keys: string[];
	};

	type Recording = {
		id: number;
		game_id: string;
		started_at: string | null;
		ended_at: string | null;
		fps: number;
		frame_count: number;
		notes: string | null;
	};

	type RecordingSummary = {
		recording: Recording;
		disk_size_bytes: number;
	};

	type TrainingResult = {
		motor_model_id: number;
		onnx_path: string;
		accuracy_keys: number;
		mse_mouse: number;
		training_time_s: number;
	};

	type TrainingStatus = {
		running: boolean;
		recording_id: number | null;
		game_id: string | null;
		epoch: number;
		epochs_total: number;
		train_loss: number;
		val_loss: number;
		accuracy_keys: number;
		mse_mouse: number;
		eta_s: number;
		error: string | null;
		loss_curve: number[];
		val_loss_curve: number[];
		result: TrainingResult | null;
	};

	let games: Game[] = $state([]);
	let recordings: RecordingSummary[] = $state([]);
	let selectedGameId = $state('');
	let selectedRecordingId = $state<number | null>(null);
	let status = $state<TrainingStatus | null>(null);
	let error = $state('');
	let starting = $state(false);
	let cancelling = $state(false);

	let epochs = $state(20);
	let batchSize = $state(32);
	let imgSize = $state(128);
	let device = $state<'auto' | 'mps' | 'cuda' | 'cpu'>('auto');

	let pollHandle: ReturnType<typeof setInterval> | null = null;

	let isRunning = $derived(status?.running === true);
	let filteredRecordings = $derived(
		selectedGameId === ''
			? recordings
			: recordings.filter((r) => r.recording.game_id === selectedGameId)
	);

	onMount(async () => {
		await Promise.all([loadGames(), loadRecordings(), refreshStatus()]);
		maybeStartPolling();
		if (filteredRecordings.length > 0 && selectedRecordingId === null) {
			selectedRecordingId = filteredRecordings[0].recording.id;
		}
	});
	onDestroy(() => stopPolling());

	function stopPolling() {
		if (pollHandle !== null) {
			clearInterval(pollHandle);
			pollHandle = null;
		}
	}

	function maybeStartPolling() {
		if (status?.running && pollHandle === null) {
			pollHandle = setInterval(refreshStatus, 1000);
		}
		if (!status?.running && pollHandle !== null) {
			stopPolling();
		}
	}

	async function loadGames() {
		try {
			const res = await fetch(`${BACKEND}/games`);
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			games = (await res.json()) as Game[];
		} catch (e) {
			error = humanizeException(e);
		}
	}

	async function loadRecordings() {
		try {
			const res = await fetch(`${BACKEND}/recordings`);
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			recordings = (await res.json()) as RecordingSummary[];
		} catch (e) {
			error = humanizeException(e);
		}
	}

	async function refreshStatus() {
		try {
			const res = await fetch(`${BACKEND}/training/status`);
			if (!res.ok) return;
			status = (await res.json()) as TrainingStatus;
			maybeStartPolling();
		} catch {
			// silent
		}
	}

	async function startTraining() {
		if (selectedRecordingId === null) return;
		error = '';
		starting = true;
		try {
			const body: Record<string, unknown> = {
				recording_id: selectedRecordingId,
				config: {
					epochs,
					batch_size: batchSize,
					img_size: imgSize,
					device: device === 'auto' ? null : device
				}
			};
			const res = await fetch(`${BACKEND}/training/start`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			status = (await res.json()) as TrainingStatus;
			maybeStartPolling();
		} catch (e) {
			error = humanizeException(e);
		} finally {
			starting = false;
		}
	}

	async function cancelTraining() {
		cancelling = true;
		try {
			const res = await fetch(`${BACKEND}/training/cancel`, { method: 'POST' });
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			status = (await res.json()) as TrainingStatus;
		} catch (e) {
			error = humanizeException(e);
		} finally {
			cancelling = false;
		}
	}

	// SVG inline pra plotar loss curve sem CDN
	function svgPolyline(values: number[], color: string): string {
		if (values.length < 2) return '';
		const W = 300;
		const H = 100;
		const PAD = 6;
		const min = Math.min(...values);
		const max = Math.max(...values);
		const range = Math.max(max - min, 1e-6);
		const pts = values
			.map((v, i) => {
				const x = PAD + ((W - 2 * PAD) * i) / (values.length - 1);
				const y = H - PAD - ((H - 2 * PAD) * (v - min)) / range;
				return `${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(' ');
		return `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" />`;
	}

	let chartHtml = $derived.by(() => {
		if (!status) return '';
		const W = 300;
		const H = 100;
		const train = svgPolyline(status.loss_curve, '#1d4ed8');
		const val = svgPolyline(status.val_loss_curve, '#b45309');
		return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="${W}" height="${H}" fill="#f9fafb" stroke="#e5e7eb" />${train}${val}</svg>`;
	});

	function fmtPct(v: number): string {
		return `${(v * 100).toFixed(1)}%`;
	}
</script>

<main>
	<header>
		<h1>Treinar motor model</h1>
		<p class="subtitle">
			Behavioral cloning: pega uma gravação e treina uma CNN pequena
			(~350k params) que prediz teclas+mouse a partir do frame. Saída:
			ONNX em <code>data/motor_models/&lt;game&gt;/&lt;rec&gt;.onnx</code>,
			usado pelo loop hierárquico (M7).
		</p>
	</header>

	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}

	<section class="layout">
		<div class="config" class:disabled={isRunning}>
			<div class="row">
				<label>
					<span>Filtrar por jogo</span>
					<select bind:value={selectedGameId} disabled={isRunning}>
						<option value="">Todos</option>
						{#each games as g (g.id)}
							<option value={g.id}>{g.name}</option>
						{/each}
					</select>
				</label>
				<label>
					<span>Gravação</span>
					<select bind:value={selectedRecordingId} disabled={isRunning}>
						{#each filteredRecordings as r (r.recording.id)}
							<option value={r.recording.id}>
								#{r.recording.id} — {r.recording.game_id} — {r.recording.frame_count} frames
							</option>
						{/each}
					</select>
				</label>
			</div>

			<div class="row limits">
				<label>
					<span>Epochs</span>
					<input
						type="number"
						bind:value={epochs}
						min="1"
						max="200"
						disabled={isRunning}
					/>
				</label>
				<label>
					<span>Batch size</span>
					<input
						type="number"
						bind:value={batchSize}
						min="1"
						max="512"
						disabled={isRunning}
					/>
				</label>
				<label>
					<span>Img size</span>
					<input
						type="number"
						bind:value={imgSize}
						min="32"
						max="512"
						step="32"
						disabled={isRunning}
					/>
				</label>
				<label>
					<span>Device</span>
					<select bind:value={device} disabled={isRunning}>
						<option value="auto">Auto (MPS > CUDA > CPU)</option>
						<option value="mps">MPS</option>
						<option value="cuda">CUDA</option>
						<option value="cpu">CPU</option>
					</select>
				</label>
			</div>

			<div class="controls">
				<button
					class="primary"
					onclick={startTraining}
					disabled={isRunning || starting || selectedRecordingId === null}
				>
					{starting ? 'Iniciando…' : isRunning ? 'Treinando' : 'Treinar'}
				</button>
				<button class="danger" onclick={cancelTraining} disabled={!isRunning || cancelling}>
					{cancelling ? 'Cancelando…' : 'Cancelar'}
				</button>
			</div>
		</div>

		<aside class="live">
			<h2>Status</h2>
			{#if status === null}
				<p class="muted">Carregando…</p>
			{:else if !status.running && !status.result && !status.error && status.epoch === 0}
				<p class="muted">Nenhum treino iniciado nesta sessão.</p>
			{:else}
				<div class="metrics">
					<div class="metric">
						<span class="label">Epoch</span>
						<span class="value mono">{status.epoch} / {status.epochs_total}</span>
					</div>
					<div class="metric">
						<span class="label">Train loss</span>
						<span class="value mono">{status.train_loss.toFixed(4)}</span>
					</div>
					<div class="metric">
						<span class="label">Val loss</span>
						<span class="value mono">{status.val_loss.toFixed(4)}</span>
					</div>
					<div class="metric">
						<span class="label">Accuracy keys</span>
						<span class="value mono">{fmtPct(status.accuracy_keys)}</span>
					</div>
					<div class="metric">
						<span class="label">MSE mouse</span>
						<span class="value mono">{status.mse_mouse.toFixed(4)}</span>
					</div>
					<div class="metric">
						<span class="label">ETA</span>
						<span class="value mono">{status.eta_s.toFixed(0)}s</span>
					</div>
				</div>

				{#if status.loss_curve.length >= 2}
					<div class="chart">
						<!-- eslint-disable-next-line svelte/no-at-html-tags -->
						{@html chartHtml}
						<div class="legend">
							<span class="train">— train</span>
							<span class="val">— val</span>
						</div>
					</div>
				{/if}

				{#if status.error}
					<p class="error">Erro: {status.error}</p>
				{/if}

				{#if status.result}
					<div class="result">
						<h3>Treino concluído ✓</h3>
						<p>
							<strong>Motor model #{status.result.motor_model_id}</strong>
						</p>
						<p>
							Accuracy keys: <strong>{fmtPct(status.result.accuracy_keys)}</strong> |
							MSE mouse: {status.result.mse_mouse.toFixed(4)} | Tempo:
							{status.result.training_time_s.toFixed(1)}s
						</p>
						<p><code>{status.result.onnx_path}</code></p>
					</div>
				{/if}
			{/if}
		</aside>
	</section>
</main>

<style>
	main {
		max-width: 1200px;
		margin: 0 auto;
		padding: 1.5rem 1.5rem 3rem;
		font-family:
			ui-sans-serif,
			system-ui,
			-apple-system,
			'Segoe UI',
			sans-serif;
		color: #1f2937;
	}

	header {
		margin-bottom: 1.25rem;
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

	h3 {
		margin: 0.5rem 0 0.25rem;
		font-size: 1rem;
		color: #065f46;
	}

	.subtitle {
		margin: 0;
		color: #6b7280;
		line-height: 1.4;
	}

	.layout {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.25rem;
	}

	@media (max-width: 900px) {
		.layout {
			grid-template-columns: 1fr;
		}
	}

	.config {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 1.25rem;
		background: #f9fafb;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
	}

	.config.disabled {
		opacity: 0.7;
	}

	.row {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.row.limits {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.85rem;
		color: #374151;
	}

	input[type='number'],
	select {
		padding: 0.4rem 0.5rem;
		border: 1px solid #d1d5db;
		border-radius: 6px;
		font-size: 0.95rem;
		background: white;
	}

	.controls {
		display: flex;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}

	button {
		padding: 0.6rem 1.2rem;
		border-radius: 6px;
		border: 1px solid transparent;
		font-size: 0.95rem;
		font-weight: 600;
		cursor: pointer;
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	button.primary {
		background: #1d4ed8;
		color: white;
	}

	button.primary:hover {
		background: #1e40af;
	}

	button.danger {
		background: #fef2f2;
		color: #991b1b;
		border-color: #fca5a5;
	}

	button.danger:hover {
		background: #fee2e2;
	}

	.live {
		padding: 1rem 1.25rem;
		background: #f9fafb;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
	}

	.metrics {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
		gap: 0.6rem;
		margin-bottom: 0.75rem;
	}

	.metric {
		display: flex;
		flex-direction: column;
	}

	.metric .label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: #6b7280;
	}

	.metric .value {
		font-size: 1rem;
		font-weight: 600;
		color: #1f2937;
	}

	.mono {
		font-family: ui-monospace, monospace;
	}

	.chart {
		margin: 0.5rem 0;
	}

	.legend {
		font-size: 0.75rem;
		display: flex;
		gap: 0.75rem;
		margin-top: 0.25rem;
	}

	.legend .train {
		color: #1d4ed8;
	}

	.legend .val {
		color: #b45309;
	}

	.result {
		margin-top: 0.5rem;
		padding: 0.75rem 1rem;
		background: #ecfdf5;
		border: 1px solid #6ee7b7;
		border-radius: 6px;
		color: #065f46;
		font-size: 0.9rem;
	}

	.result code {
		background: #064e3b;
		color: #d1fae5;
		padding: 0.05rem 0.4rem;
		border-radius: 4px;
		font-size: 0.75rem;
		word-break: break-all;
	}

	.error {
		margin: 1rem 0;
		padding: 0.75rem 1rem;
		background: #fee2e2;
		border: 1px solid #fca5a5;
		border-radius: 6px;
		color: #991b1b;
	}

	.muted {
		color: #9ca3af;
		font-style: italic;
	}

	code {
		background: #1f2937;
		color: #f9fafb;
		padding: 0.1rem 0.4rem;
		border-radius: 4px;
		font-size: 0.85rem;
	}
</style>
