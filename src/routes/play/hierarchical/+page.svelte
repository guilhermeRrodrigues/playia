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
		created_at: string | null;
	};

	type MotorModel = {
		id: number;
		game_id: string;
		recording_id: number;
		onnx_path: string;
		accuracy: number;
		trained_at: string | null;
		version: number;
	};

	type Intention = {
		text: string;
		params: Record<string, unknown>;
		issued_at: string;
		ttl_s: number;
	};

	type HSessionState = {
		status: 'idle' | 'running' | 'stopped' | 'error';
		game: string | null;
		region: [number, number, number, number] | null;
		motor_model_id: number | null;
		motor_accuracy: number | null;
		current_intention: Intention | null;
		intentions_history: Intention[];
		actions_per_second: number;
		total_actions: number;
		last_frame_b64: string | null;
		started_at: string | null;
		finished_at: string | null;
		stop_reason: string | null;
		error: string | null;
	};

	let games: Game[] = $state([]);
	let motorModels: MotorModel[] = $state([]);

	// Jogos elegíveis: fast_realtime + tem motor_model treinado.
	let eligibleGames = $derived(
		games
			.filter((g) => g.tempo === 'fast_realtime')
			.filter((g) => motorModels.some((m) => m.game_id === g.id))
	);

	let selectedGame = $state('chrome-dino');
	let selectedGameObj = $derived(games.find((g) => g.id === selectedGame) ?? null);
	let antiCheatBlocked = $derived(
		selectedGameObj !== null && selectedGameObj.anti_cheat !== 'none'
	);
	let acknowledgeText = $state('');

	let useRegion = $state(false);
	let regionX = $state(0);
	let regionY = $state(0);
	let regionW = $state(0);
	let regionH = $state(0);

	let maxDuration = $state(300);
	let targetFps = $state(30);

	let status = $state<HSessionState | null>(null);
	let error = $state('');
	let starting = $state(false);
	let stopping = $state(false);

	let pollHandle: ReturnType<typeof setInterval> | null = null;

	let isRunning = $derived(status?.status === 'running');
	let canStart = $derived(
		!isRunning &&
			!starting &&
			selectedGame !== '' &&
			eligibleGames.some((g) => g.id === selectedGame) &&
			(!antiCheatBlocked || acknowledgeText.trim() === 'estou ciente do risco')
	);

	onMount(async () => {
		await Promise.all([loadGames(), loadMotors(), refreshStatus()]);
		if (eligibleGames.length > 0 && !eligibleGames.some((g) => g.id === selectedGame)) {
			selectedGame = eligibleGames[0].id;
		}
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
		if (status?.status === 'running' && pollHandle === null) {
			pollHandle = setInterval(refreshStatus, 1000);
		}
		if (status?.status !== 'running' && pollHandle !== null) {
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

	async function loadMotors() {
		try {
			const res = await fetch(`${BACKEND}/motor-models`);
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			motorModels = (await res.json()) as MotorModel[];
		} catch (e) {
			error = humanizeException(e);
		}
	}

	async function refreshStatus() {
		try {
			const res = await fetch(`${BACKEND}/hsession/status`);
			if (!res.ok) return;
			status = (await res.json()) as HSessionState;
			maybeStartPolling();
		} catch {
			// silent
		}
	}

	async function startSession() {
		error = '';
		starting = true;
		try {
			const body: Record<string, unknown> = {
				game_id: selectedGame,
				max_duration_s: maxDuration,
				target_fps: targetFps
			};
			if (useRegion) body.region = [regionX, regionY, regionW, regionH];
			if (antiCheatBlocked) body.acknowledge_ban_risk = acknowledgeText.trim();
			const res = await fetch(`${BACKEND}/hsession/start`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			status = (await res.json()) as HSessionState;
			maybeStartPolling();
		} catch (e) {
			error = humanizeException(e);
		} finally {
			starting = false;
		}
	}

	async function stopSession() {
		stopping = true;
		try {
			const res = await fetch(`${BACKEND}/hsession/stop`, { method: 'POST' });
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			status = (await res.json()) as HSessionState;
		} catch (e) {
			error = humanizeException(e);
		} finally {
			stopping = false;
		}
	}

	let elapsedSec = $derived.by(() => {
		if (!status?.started_at) return 0;
		const start = new Date(status.started_at).getTime();
		const end = status.finished_at
			? new Date(status.finished_at).getTime()
			: Date.now();
		return Math.max(0, Math.floor((end - start) / 1000));
	});

	function fmtElapsed(s: number): string {
		const m = Math.floor(s / 60);
		const sec = s % 60;
		return `${m}:${sec.toString().padStart(2, '0')}`;
	}

	function intentionsTail(): Intention[] {
		if (!status) return [];
		const list = status.intentions_history;
		return list.slice(Math.max(0, list.length - 5));
	}
</script>

<nav class="tabs">
	<a href="/play" class="tab">Turn-based (M3)</a>
	<a href="/play/hierarchical" class="tab active" aria-current="page">Hierárquico (M7)</a>
</nav>

<aside class="banner" role="note">
	Modo hierárquico: o <strong>VLM estrategista</strong> define uma intenção
	em pt-br a cada 5-15s, enquanto o <strong>motor model ONNX</strong> joga a
	30Hz a partir do frame. Na v0.1 o motor não usa a intenção como input;
	ela aparece aqui só para debug.
</aside>

<main>
	<header>
		<h1>Hierárquico</h1>
		<p class="subtitle">
			Loop VLM (lento) + motor (rápido) controla um jogo fast_realtime.
			Pré-condição: ter um motor_model treinado em <a href="/train">/train</a>.
		</p>
	</header>

	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}

	{#if eligibleGames.length === 0}
		<p class="muted">
			Nenhum jogo fast_realtime tem motor_model treinado ainda. Grave uma
			gravação em <a href="/record">/record</a> e treine em <a href="/train">/train</a>
			antes.
		</p>
	{:else}
		<section class="config" class:disabled={isRunning}>
			<div class="row">
				<label>
					<span>Jogo (fast_realtime + motor treinado)</span>
					<select bind:value={selectedGame} disabled={isRunning}>
						{#each eligibleGames as g (g.id)}
							<option value={g.id}>{g.name}</option>
						{/each}
					</select>
				</label>
				{#if selectedGameObj}
					<p class="hint">
						Abra <a href={selectedGameObj.url} target="_blank" rel="noreferrer"
							>{selectedGameObj.url}</a
						>
						e foque a janela antes de iniciar.
					</p>
				{/if}
			</div>

			{#if antiCheatBlocked && selectedGameObj}
				<aside class="anti-cheat-warning" role="alert">
					<strong>⚠ AVISO DE BAN</strong> — o jogo
					<code>{selectedGameObj.id}</code> usa
					<code>{selectedGameObj.anti_cheat}</code>. Automação detectada = ban
					da conta (e possivelmente do HWID). Para liberar, digite EXATAMENTE
					<code>estou ciente do risco</code> abaixo:
					<input
						type="text"
						bind:value={acknowledgeText}
						placeholder="estou ciente do risco"
						disabled={isRunning}
					/>
				</aside>
			{/if}

			<div class="row limits">
				<label>
					<span>Duração máx (s)</span>
					<input
						type="number"
						bind:value={maxDuration}
						min="1"
						max="86400"
						disabled={isRunning}
					/>
				</label>
				<label>
					<span>Target FPS</span>
					<input
						type="number"
						bind:value={targetFps}
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

		<p class="focus-hint">
			<strong>Antes de clicar Iniciar:</strong> foque a janela do jogo.
			Depois clique Iniciar — você tem 3 segundos pra voltar pro jogo
			antes da primeira tecla. Sem foco correto, as teclas vão pra
			janela do PlayIA e nada acontece no jogo.
		</p>

		<div class="controls">
			<button class="start" onclick={startSession} disabled={!canStart}>
				{starting
					? 'Iniciando…'
					: isRunning
						? 'Sessão em andamento'
						: antiCheatBlocked && acknowledgeText.trim() !== 'estou ciente do risco'
							? 'Digite a frase de risco acima'
							: 'INICIAR'}
			</button>
			<button class="stop" onclick={stopSession} disabled={!isRunning || stopping}>
				{stopping ? 'PARANDO…' : 'PARAR'}
			</button>
		</div>
	{/if}

	<section class="live">
		<h2>Status</h2>
		{#if status === null}
			<p class="muted">Carregando…</p>
		{:else}
			<div class="status-row">
				<span class="badge badge-{status.status}">{status.status.toUpperCase()}</span>
				{#if status.stop_reason}
					<small>motivo: {status.stop_reason}</small>
				{/if}
				{#if status.motor_model_id !== null}
					<small>motor #{status.motor_model_id}</small>
				{/if}
				{#if status.motor_accuracy !== null}
					<small>accuracy: {(status.motor_accuracy * 100).toFixed(1)}%</small>
				{/if}
				<small>ações: {status.total_actions}</small>
				<small>FPS real: {status.actions_per_second.toFixed(1)}</small>
				<small>tempo: {fmtElapsed(elapsedSec)}</small>
			</div>

			{#if status.error}
				<p class="error">Erro: {status.error}</p>
			{/if}

			{#if status.current_intention}
				<div class="intention-current">
					<small class="label">Intenção atual</small>
					<p class="intention-text">{status.current_intention.text}</p>
					<small class="ttl"
						>ttl: {status.current_intention.ttl_s}s · publicada em {new Date(
							status.current_intention.issued_at
						).toLocaleTimeString('pt-BR')}</small
					>
				</div>
			{/if}

			{#if status.last_frame_b64}
				<figure>
					<img
						src={`data:image/png;base64,${status.last_frame_b64}`}
						alt="Tela vista pelo motor"
					/>
					<figcaption>O que o motor acabou de ver{status.region ? ' (recortado)' : ''}</figcaption>
				</figure>
			{/if}

			{#if intentionsTail().length > 0}
				<div class="history">
					<small class="label">Últimas intenções</small>
					<ul>
						{#each intentionsTail() as it (it.issued_at)}
							<li>
								<code>{new Date(it.issued_at).toLocaleTimeString('pt-BR')}</code>
								{it.text}
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		{/if}
	</section>
</main>

<style>
	.tabs {
		display: flex;
		gap: 0;
		max-width: 1100px;
		margin: 0 auto;
		padding: 0 1.5rem;
		border-bottom: 1px solid #e5e7eb;
	}

	.tab {
		padding: 0.65rem 1.1rem;
		font-size: 0.9rem;
		font-weight: 600;
		color: #6b7280;
		text-decoration: none;
		border-bottom: 3px solid transparent;
		transition:
			color 120ms ease,
			border-color 120ms ease;
	}

	.tab:hover {
		color: #1f2937;
	}

	.tab.active {
		color: #047857;
		border-bottom-color: #047857;
	}

	.banner {
		max-width: 1100px;
		margin: 0.75rem auto 0;
		padding: 0.75rem 1.5rem;
		background: #eff6ff;
		border: 1px solid #bfdbfe;
		color: #1e3a8a;
		font-size: 0.9rem;
		line-height: 1.4;
		border-radius: 0 0 8px 8px;
	}

	main {
		max-width: 1100px;
		margin: 0 auto;
		padding: 1rem 1.5rem 3rem;
		font-family:
			ui-sans-serif,
			system-ui,
			-apple-system,
			'Segoe UI',
			sans-serif;
		color: #1f2937;
	}

	header {
		margin-bottom: 1rem;
	}

	h1 {
		margin: 0 0 0.25rem;
		font-size: 1.5rem;
	}

	h2 {
		margin: 1.25rem 0 0.5rem;
		font-size: 1.05rem;
		color: #374151;
	}

	.subtitle {
		margin: 0;
		color: #6b7280;
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
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 0.75rem;
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
	input[type='text'],
	select {
		padding: 0.4rem 0.5rem;
		border: 1px solid #d1d5db;
		border-radius: 6px;
		font-size: 0.95rem;
		background: white;
		font-family: inherit;
	}

	input:disabled,
	select:disabled {
		background: #f3f4f6;
	}

	.anti-cheat-warning {
		padding: 0.75rem 1rem;
		background: #7f1d1d;
		color: #fef2f2;
		border-radius: 8px;
		line-height: 1.4;
		font-size: 0.9rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.anti-cheat-warning code {
		background: #450a0a;
		color: #fecaca;
		padding: 0.05rem 0.35rem;
		border-radius: 4px;
		font-size: 0.85rem;
	}

	.anti-cheat-warning input {
		width: 100%;
	}

	.hint {
		margin: 0;
		font-size: 0.85rem;
		color: #6b7280;
	}

	.focus-hint {
		margin: 1rem 0 0;
		padding: 0.6rem 0.9rem;
		background: #fef3c7;
		border: 1px solid #fde68a;
		border-radius: 6px;
		font-size: 0.85rem;
		color: #78350f;
		line-height: 1.4;
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
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	button.start {
		background: #047857;
		color: white;
		font-size: 1.15rem;
		padding: 1rem 2rem;
	}

	button.start:hover:not(:disabled) {
		background: #065f46;
	}

	button.stop {
		background: #b91c1c;
		color: white;
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

	.live {
		margin-top: 1.5rem;
	}

	.status-row {
		display: flex;
		gap: 0.6rem;
		flex-wrap: wrap;
		align-items: center;
		font-size: 0.85rem;
		color: #4b5563;
	}

	.badge {
		display: inline-block;
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.04em;
		border: 1px solid transparent;
	}

	.badge-idle {
		background: #f3f4f6;
		color: #6b7280;
		border-color: #d1d5db;
	}

	.badge-running {
		background: #ecfdf5;
		color: #065f46;
		border-color: #6ee7b7;
	}

	.badge-stopped {
		background: #e0e7ff;
		color: #3730a3;
		border-color: #c7d2fe;
	}

	.badge-error {
		background: #fef2f2;
		color: #991b1b;
		border-color: #fca5a5;
	}

	.intention-current {
		margin: 1rem 0;
		padding: 1rem 1.25rem;
		background: #ecfdf5;
		border: 1px solid #6ee7b7;
		border-radius: 8px;
	}

	.intention-text {
		margin: 0.4rem 0 0;
		font-size: 1.4rem;
		font-weight: 600;
		color: #065f46;
		line-height: 1.3;
	}

	.intention-current .label,
	.history .label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: #6b7280;
	}

	.intention-current .ttl {
		font-size: 0.75rem;
		color: #047857;
	}

	figure {
		margin: 1rem 0;
	}

	img {
		max-width: 100%;
		height: auto;
		border: 1px solid #d1d5db;
		border-radius: 6px;
	}

	figcaption {
		font-size: 0.8rem;
		color: #6b7280;
		margin-top: 0.25rem;
	}

	.history ul {
		list-style: none;
		padding: 0;
		margin: 0.4rem 0 0;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		font-size: 0.85rem;
		color: #4b5563;
	}

	.history code {
		background: #1f2937;
		color: #f9fafb;
		padding: 0.05rem 0.4rem;
		border-radius: 4px;
		font-size: 0.75rem;
		margin-right: 0.4rem;
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

	a {
		color: #1d4ed8;
		text-decoration: none;
	}

	a:hover {
		text-decoration: underline;
	}

	code {
		background: #1f2937;
		color: #f9fafb;
		padding: 0.1rem 0.4rem;
		border-radius: 4px;
		font-size: 0.85rem;
	}
</style>
