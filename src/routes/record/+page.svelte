<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { BACKEND, humanizeError, humanizeException } from '$lib/http';

	type Tempo = 'turn_based' | 'slow_realtime' | 'fast_realtime';
	type AntiCheat =
		| 'none'
		| 'unknown'
		| 'hyperion'
		| 'eac'
		| 'battleye'
		| 'vanguard'
		| 'other';

	type Game = {
		id: string;
		name: string;
		url: string;
		tempo: Tempo;
		anti_cheat: AntiCheat;
		allowed_keys: string[];
		goal: string;
		notes: string | null;
	};

	type RecordingStatus = {
		running: boolean;
		recording_id: number | null;
		game_id: string | null;
		fps_target: number;
		fps_real: number;
		frames_captured: number;
		started_at: string | null;
		finished_at: string | null;
		region: [number, number, number, number] | null;
		error: string | null;
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

	let games: Game[] = $state([]);
	let recordings: RecordingSummary[] = $state([]);
	let selectedGame = $state('chrome-dino');
	let selectedGameObj = $derived(games.find((g) => g.id === selectedGame) ?? null);
	let antiCheatBlocked = $derived(
		selectedGameObj !== null && selectedGameObj.anti_cheat !== 'none'
	);

	let fps = $state(30);
	let useRegion = $state(false);
	let regionX = $state(0);
	let regionY = $state(0);
	let regionW = $state(0);
	let regionH = $state(0);

	let status = $state<RecordingStatus | null>(null);
	let error = $state('');
	let starting = $state(false);
	let stopping = $state(false);

	let pollHandle: ReturnType<typeof setInterval> | null = null;

	const FETCH_GAMES = `${BACKEND}/games`;
	const FETCH_RECORDINGS = `${BACKEND}/recordings`;
	const REC_STATUS = `${BACKEND}/recording/status`;
	const REC_START = `${BACKEND}/recording/start`;
	const REC_STOP = `${BACKEND}/recording/stop`;

	let isRunning = $derived(status?.running === true);

	onMount(async () => {
		await Promise.all([loadGames(), loadRecordings(), refreshStatus()]);
		maybeStartPolling();
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
			pollHandle = setInterval(async () => {
				await refreshStatus();
				if (!status?.running) {
					await loadRecordings();
					stopPolling();
				}
			}, 1000);
		}
	}

	async function loadGames() {
		try {
			const res = await fetch(FETCH_GAMES);
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			games = (await res.json()) as Game[];
			if (games.length > 0 && !games.find((g) => g.id === selectedGame)) {
				selectedGame = games[0].id;
			}
		} catch (e) {
			error = humanizeException(e);
		}
	}

	async function loadRecordings() {
		try {
			const res = await fetch(FETCH_RECORDINGS);
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
			const res = await fetch(REC_STATUS);
			if (!res.ok) return;
			status = (await res.json()) as RecordingStatus;
		} catch {
			// silent — polling
		}
	}

	async function startRecording() {
		error = '';
		starting = true;
		try {
			const body: Record<string, unknown> = {
				game_id: selectedGame,
				fps
			};
			if (useRegion) body.region = [regionX, regionY, regionW, regionH];
			const res = await fetch(REC_START, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			status = (await res.json()) as RecordingStatus;
			maybeStartPolling();
		} catch (e) {
			error = humanizeException(e);
		} finally {
			starting = false;
		}
	}

	async function stopRecording() {
		stopping = true;
		try {
			const res = await fetch(REC_STOP, { method: 'POST' });
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			status = (await res.json()) as RecordingStatus;
			await loadRecordings();
		} catch (e) {
			error = humanizeException(e);
		} finally {
			stopping = false;
		}
	}

	async function deleteRecording(id: number) {
		if (!confirm(`Apagar gravação #${id}? PNGs em disco vão junto.`)) return;
		error = '';
		try {
			const res = await fetch(`${BACKEND}/recordings/${id}`, {
				method: 'DELETE',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ confirm: true })
			});
			if (!res.ok && res.status !== 204) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			await loadRecordings();
		} catch (e) {
			error = humanizeException(e);
		}
	}

	let elapsedSec = $derived.by(() => {
		if (!status?.started_at) return 0;
		const start = new Date(status.started_at).getTime();
		const end = status.finished_at ? new Date(status.finished_at).getTime() : Date.now();
		return Math.max(0, Math.floor((end - start) / 1000));
	});

	function fmtElapsed(s: number): string {
		const m = Math.floor(s / 60);
		const sec = s % 60;
		return `${m}:${sec.toString().padStart(2, '0')}`;
	}

	function fmtMB(bytes: number): string {
		const mb = bytes / (1024 * 1024);
		if (mb >= 100) return `${Math.round(mb)} MB`;
		return `${mb.toFixed(1)} MB`;
	}

	function fmtTimestamp(s: string | null): string {
		if (!s) return '—';
		return new Date(s).toLocaleString('pt-BR', {
			day: '2-digit',
			month: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
</script>

{#if antiCheatBlocked && selectedGameObj}
	<aside class="anti-cheat-warning" role="alert">
		<strong>⚠ AVISO DE BAN</strong> — o jogo selecionado
		(<code>{selectedGameObj.id}</code>) usa
		<code>{selectedGameObj.anti_cheat}</code>. Watch-me-play não toca em input
		(só observa), mas é boa prática <strong>não rodar a captura com a conta
		principal</strong> nesses jogos.
	</aside>
{/if}

<main>
	<header>
		<h1>Gravar</h1>
		<p class="subtitle">
			A IA observa você jogando: salva frame + estado de teclado/mouse a
			cada tick em <code>~/Library/Application Support/PlayIA/data/recordings/</code>.
			Esse dataset alimenta o treinador do motor model (M6).
		</p>
		<p class="subtitle hint-perms">
			macOS: precisa de <em>Input Monitoring</em> liberado em System
			Settings → Privacy & Security pro pynput receber teclas/mouse fora
			do app.
		</p>
	</header>

	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}

	<section class="layout">
		<div class="capture">
			<section class="config" class:disabled={isRunning}>
				<div class="row">
					<label>
						<span>Jogo</span>
						<select bind:value={selectedGame} disabled={isRunning}>
							{#each games as g (g.id)}
								<option value={g.id}>{g.name} — {g.tempo}</option>
							{/each}
						</select>
					</label>
					{#if selectedGameObj}
						<p class="hint">
							Abra <a
								href={selectedGameObj.url}
								target="_blank"
								rel="noreferrer">{selectedGameObj.url}</a
							>
							e foque a janela antes de começar.
						</p>
					{/if}
				</div>

				<div class="row limits">
					<label>
						<span>FPS</span>
						<input
							type="number"
							bind:value={fps}
							min="1"
							max="60"
							disabled={isRunning}
						/>
					</label>
					<label class="checkbox">
						<input
							type="checkbox"
							bind:checked={useRegion}
							disabled={isRunning}
						/>
						<span>Recortar região</span>
					</label>
				</div>

				{#if useRegion}
					<div class="region-grid">
						<label
							><span>x</span><input
								type="number"
								bind:value={regionX}
								min="0"
								disabled={isRunning}
							/></label
						>
						<label
							><span>y</span><input
								type="number"
								bind:value={regionY}
								min="0"
								disabled={isRunning}
							/></label
						>
						<label
							><span>largura</span><input
								type="number"
								bind:value={regionW}
								min="1"
								disabled={isRunning}
							/></label
						>
						<label
							><span>altura</span><input
								type="number"
								bind:value={regionH}
								min="1"
								disabled={isRunning}
							/></label
						>
					</div>
				{/if}
			</section>

			<div class="controls">
				<button
					class="record"
					onclick={startRecording}
					disabled={isRunning || starting || games.length === 0}
				>
					{starting ? 'Iniciando…' : isRunning ? 'GRAVANDO' : '● GRAVAR'}
				</button>
				<button
					class="stop"
					onclick={stopRecording}
					disabled={!isRunning || stopping}
				>
					{stopping ? 'PARANDO…' : '■ PARAR'}
				</button>
			</div>

			<section class="live">
				<h2>Status</h2>
				{#if status === null}
					<p class="muted">Carregando…</p>
				{:else}
					<div class="metrics">
						<div class="metric">
							<span class="label">Estado</span>
							<span class="value badge badge-{status.running ? 'on' : 'off'}">
								{status.running ? 'GRAVANDO' : 'parado'}
							</span>
						</div>
						<div class="metric">
							<span class="label">FPS real</span>
							<span class="value mono">{status.fps_real.toFixed(1)}</span>
						</div>
						<div class="metric">
							<span class="label">Frames</span>
							<span class="value mono">{status.frames_captured}</span>
						</div>
						<div class="metric">
							<span class="label">Tempo</span>
							<span class="value mono">{fmtElapsed(elapsedSec)}</span>
						</div>
						{#if status.recording_id !== null}
							<div class="metric">
								<span class="label">rec_id</span>
								<span class="value mono">#{status.recording_id}</span>
							</div>
						{/if}
					</div>
					{#if status.error}
						<p class="error">Erro: {status.error}</p>
					{/if}
				{/if}
			</section>
		</div>

		<aside class="recordings">
			<h2>Gravações</h2>
			{#if recordings.length === 0}
				<p class="muted">Nenhuma gravação ainda.</p>
			{:else}
				<ul class="rec-list">
					{#each recordings as r (r.recording.id)}
						<li>
							<div class="rec-head">
								<strong>#{r.recording.id}</strong>
								<code>{r.recording.game_id}</code>
							</div>
							<div class="rec-meta">
								<span>{r.recording.frame_count} frames @ {r.recording.fps}fps</span>
								<span>{fmtMB(r.disk_size_bytes)}</span>
								<span>{fmtTimestamp(r.recording.started_at)}</span>
							</div>
							<div class="rec-actions">
								<button
									class="danger"
									onclick={() => r.recording.id !== null && deleteRecording(r.recording.id)}
								>
									Apagar
								</button>
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</aside>
	</section>
</main>

<style>
	.anti-cheat-warning {
		position: sticky;
		top: 0;
		z-index: 10;
		background: #7f1d1d;
		color: #fef2f2;
		padding: 0.75rem 1.5rem;
		font-size: 0.9rem;
		line-height: 1.4;
		border-bottom: 2px solid #450a0a;
	}

	.anti-cheat-warning code {
		background: #450a0a;
		color: #fecaca;
		padding: 0.05rem 0.35rem;
		border-radius: 4px;
	}

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
		margin: 1.25rem 0 0.5rem;
		font-size: 1.1rem;
		color: #374151;
	}

	.subtitle {
		margin: 0;
		color: #6b7280;
		line-height: 1.4;
	}

	.subtitle.hint-perms {
		font-size: 0.85rem;
		margin-top: 0.4rem;
	}

	.layout {
		display: grid;
		grid-template-columns: 2fr 1fr;
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
		flex-direction: row;
		flex-wrap: wrap;
		gap: 1rem;
		align-items: flex-end;
	}

	.region-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.5rem;
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.85rem;
		color: #374151;
	}

	label.checkbox {
		flex-direction: row;
		align-items: center;
		gap: 0.5rem;
	}

	input[type='number'],
	select {
		padding: 0.4rem 0.5rem;
		border: 1px solid #d1d5db;
		border-radius: 6px;
		font-size: 0.95rem;
		background: white;
	}

	input:disabled,
	select:disabled {
		background: #f3f4f6;
	}

	.hint {
		margin: 0;
		font-size: 0.85rem;
		color: #6b7280;
	}

	.hint a {
		color: #1d4ed8;
	}

	.controls {
		display: flex;
		gap: 0.75rem;
		margin: 1rem 0;
	}

	button {
		font-size: 1rem;
		padding: 0.85rem 1.5rem;
		border-radius: 8px;
		border: 1px solid transparent;
		cursor: pointer;
		font-weight: 700;
		letter-spacing: 0.04em;
		transition: background 120ms ease;
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	button.record {
		background: #047857;
		color: white;
		border-color: #047857;
		font-size: 1.15rem;
		padding: 1rem 2rem;
	}

	button.record:hover:not(:disabled) {
		background: #065f46;
	}

	button.stop {
		background: #b91c1c;
		color: white;
		border-color: #b91c1c;
		font-size: 1.15rem;
		padding: 1rem 2rem;
	}

	button.stop:not(:disabled) {
		animation: pulse 1.6s ease-in-out infinite;
	}

	button.stop:hover:not(:disabled) {
		background: #991b1b;
	}

	@keyframes pulse {
		0%,
		100% {
			box-shadow: 0 0 0 0 rgba(185, 28, 28, 0);
		}
		50% {
			box-shadow: 0 0 0 8px rgba(185, 28, 28, 0.18);
		}
	}

	button.danger {
		background: #fef2f2;
		color: #991b1b;
		border-color: #fca5a5;
		font-size: 0.85rem;
		padding: 0.35rem 0.7rem;
	}

	button.danger:hover {
		background: #fee2e2;
	}

	.live {
		margin-top: 0.5rem;
	}

	.metrics {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
		gap: 0.75rem;
		padding: 1rem;
		background: #f9fafb;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
	}

	.metric {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.metric .label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: #6b7280;
	}

	.metric .value {
		font-size: 1.05rem;
		font-weight: 600;
		color: #1f2937;
	}

	.metric .value.mono {
		font-family: ui-monospace, monospace;
	}

	.badge {
		display: inline-block;
		padding: 0.15rem 0.6rem;
		border-radius: 999px;
		font-size: 0.8rem;
		font-weight: 600;
		border: 1px solid transparent;
		width: fit-content;
	}

	.badge-on {
		background: #ecfdf5;
		color: #065f46;
		border-color: #6ee7b7;
	}

	.badge-off {
		background: #f3f4f6;
		color: #4b5563;
		border-color: #d1d5db;
	}

	.recordings {
		padding: 1rem 1.25rem;
		background: #f9fafb;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
	}

	.rec-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.rec-list li {
		padding: 0.6rem 0.8rem;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 6px;
	}

	.rec-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.5rem;
	}

	.rec-head code {
		background: #1f2937;
		color: #f9fafb;
		padding: 0.1rem 0.4rem;
		border-radius: 4px;
		font-size: 0.8rem;
	}

	.rec-meta {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin: 0.3rem 0;
		font-size: 0.8rem;
		color: #4b5563;
	}

	.rec-actions {
		display: flex;
		justify-content: flex-end;
	}

	.error {
		margin: 1rem 0;
		padding: 0.75rem 1rem;
		background: #fee2e2;
		border: 1px solid #fca5a5;
		border-radius: 6px;
		color: #991b1b;
		white-space: pre-wrap;
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
