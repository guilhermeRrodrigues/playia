<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { BACKEND, humanizeError, humanizeException } from '$lib/http';

	type Action = {
		kind: 'key' | 'click' | 'wait' | 'stop';
		key: string | null;
		x: number | null;
		y: number | null;
		duration_ms: number | null;
		reason: string;
	};

	type SessionState = {
		status: 'idle' | 'running' | 'paused' | 'stopped' | 'error';
		game: string | null;
		region: [number, number, number, number] | null;
		started_at: string | null;
		finished_at: string | null;
		actions_taken: number;
		last_action: Action | null;
		last_reason: string | null;
		history: Action[];
		last_screenshot_b64: string | null;
		stop_reason: string | null;
		error: string | null;
	};

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

	let games: Game[] = $state([]);
	let selectedGame = $state('2048');
	let selectedGameObj = $derived(games.find((g) => g.id === selectedGame) ?? null);
	let antiCheatBlocked = $derived(
		selectedGameObj !== null && selectedGameObj.anti_cheat !== 'none'
	);

	// region em campos separados pra evitar bind em array
	let regionX = $state(0);
	let regionY = $state(0);
	let regionW = $state(0);
	let regionH = $state(0);
	let useRegion = $state(false);

	let maxActions = $state(50);
	let maxDuration = $state(600);
	let stepDelay = $state(300);

	let session = $state<SessionState | null>(null);
	let startError = $state('');
	let stopping = $state(false);
	let starting = $state(false);

	let pollHandle: ReturnType<typeof setInterval> | null = null;

	// O modo turn-based (M3) só aceita games com tempo=turn_based.
	// Filtramos no servidor para o dropdown não mostrar opções inválidas.
	const FETCH_GAMES = `${BACKEND}/games?tempo=turn_based`;
	const SESSION_STATUS = `${BACKEND}/session/status`;
	const SESSION_START = `${BACKEND}/session/start`;
	const SESSION_STOP = `${BACKEND}/session/stop`;

	onMount(async () => {
		await Promise.all([loadGames(), refreshStatus()]);
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
		if (session?.status === 'running' && pollHandle === null) {
			pollHandle = setInterval(refreshStatus, 1000);
		}
		if (session?.status !== 'running' && pollHandle !== null) {
			stopPolling();
		}
	}

	async function loadGames() {
		try {
			const res = await fetch(FETCH_GAMES);
			if (!res.ok) {
				startError = humanizeError(res.status, await res.text());
				return;
			}
			games = (await res.json()) as Game[];
			if (games.length > 0 && !games.find((g) => g.id === selectedGame)) {
				selectedGame = games[0].id;
			}
		} catch (e) {
			startError = `Backend offline: ${humanizeException(e)}`;
		}
	}

	async function refreshStatus() {
		try {
			const res = await fetch(SESSION_STATUS);
			if (!res.ok) return;
			session = (await res.json()) as SessionState;
			maybeStartPolling();
		} catch {
			// silêncio: polling
		}
	}

	async function startSession() {
		startError = '';
		starting = true;
		try {
			const body: Record<string, unknown> = {
				game: selectedGame,
				max_actions: maxActions,
				max_duration_s: maxDuration,
				step_delay_ms: stepDelay
			};
			if (useRegion) {
				body.region = [regionX, regionY, regionW, regionH];
			}
			const res = await fetch(SESSION_START, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			const text = await res.text();
			if (!res.ok) {
				startError = humanizeError(res.status, text);
				return;
			}
			session = JSON.parse(text) as SessionState;
			maybeStartPolling();
		} catch (e) {
			startError = humanizeException(e);
		} finally {
			starting = false;
		}
	}

	async function stopSession() {
		stopping = true;
		try {
			const res = await fetch(SESSION_STOP, { method: 'POST' });
			if (!res.ok) {
				startError = humanizeError(res.status, await res.text());
				return;
			}
			session = (await res.json()) as SessionState;
			// continua polling até status sair de running
			maybeStartPolling();
		} catch (e) {
			startError = humanizeException(e);
		} finally {
			stopping = false;
		}
	}

	// derivados
	let isRunning = $derived(session?.status === 'running');
	let elapsedSec = $derived.by(() => {
		if (!session?.started_at) return 0;
		const start = new Date(session.started_at).getTime();
		const end = session.finished_at ? new Date(session.finished_at).getTime() : Date.now();
		return Math.max(0, Math.floor((end - start) / 1000));
	});

	function fmtElapsed(s: number): string {
		const m = Math.floor(s / 60);
		const sec = s % 60;
		return `${m}:${sec.toString().padStart(2, '0')}`;
	}
</script>

<nav class="tabs">
	<a href="/play" class="tab active" aria-current="page">Turn-based (M3)</a>
	<a href="/play/hierarchical" class="tab">Hierárquico (M7)</a>
</nav>

<aside class="warning" role="alert">
	<strong>Atenção:</strong> não use o PlayIA em jogos online com anti-cheat (Vanguard,
	EAC, BattlEye, Hyperion). Single-player ou browser apenas. Mover o mouse para
	o canto superior esquerdo aborta a sessão (pyautogui failsafe).
</aside>

<main>
	<header>
		<h1>Play</h1>
		<p class="subtitle">
			A IA vê a tela e joga sozinha. Pré-condição: <code>ollama serve</code> + modelo baixado.
		</p>
	</header>

	{#if startError}
		<p class="error">{startError}</p>
	{/if}

	<section class="config" class:disabled={isRunning}>
		<div class="row">
			<label>
				<span>Jogo (apenas turn-based; outros tempos aguardam M7)</span>
				<select bind:value={selectedGame} disabled={isRunning}>
					{#each games as g (g.id)}
						<option value={g.id}>{g.name}</option>
					{/each}
				</select>
			</label>

			{#if selectedGameObj}
				<p class="hint">
					Abra <a href={selectedGameObj.url} target="_blank" rel="noreferrer"
						>{selectedGameObj.url}</a
					>
					em outra janela e foque-a antes de iniciar.
				</p>
			{/if}

			{#if antiCheatBlocked && selectedGameObj}
				<aside class="anti-cheat-block" role="alert">
					<strong>⚠ Sessão bloqueada — anti-cheat detectado</strong>
					<p>
						O jogo <code>{selectedGameObj.id}</code> tem
						<code>anti_cheat={selectedGameObj.anti_cheat}</code>. Automação
						detectada = ban da conta. A UI não libera bypass aqui; se
						realmente quiser tentar, use a API
						<code>POST /session/start</code> com
						<code>acknowledge_ban_risk: "estou ciente do risco"</code>.
					</p>
				</aside>
			{/if}
		</div>

		<div class="row">
			<label class="checkbox">
				<input type="checkbox" bind:checked={useRegion} disabled={isRunning} />
				<span>Recortar região do jogo (x, y, largura, altura em pixels)</span>
			</label>
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
		</div>

		<div class="row limits">
			<label
				><span>Máx. ações</span><input
					type="number"
					bind:value={maxActions}
					min="1"
					max="10000"
					disabled={isRunning}
				/></label
			>
			<label
				><span>Máx. duração (s)</span><input
					type="number"
					bind:value={maxDuration}
					min="1"
					max="86400"
					disabled={isRunning}
				/></label
			>
			<label
				><span>Delay entre ações (ms)</span><input
					type="number"
					bind:value={stepDelay}
					min="0"
					max="60000"
					disabled={isRunning}
				/></label
			>
		</div>
	</section>

	<p class="focus-hint">
		<strong>Antes de clicar Iniciar:</strong> deixe a janela do jogo
		(2048 no Chrome) visível e foque-a. Depois clique Iniciar — você
		tem 3 segundos pra voltar a focar o jogo antes da primeira ação.
		Sem isso, as teclas vão para a janela do PlayIA e o jogo não muda.
	</p>

	<div class="controls">
		<button
			class="start"
			onclick={startSession}
			disabled={isRunning || starting || antiCheatBlocked || games.length === 0}
		>
			{starting
				? 'Iniciando…'
				: isRunning
					? 'Sessão em andamento'
					: antiCheatBlocked
						? 'Bloqueado (anti-cheat)'
						: 'Iniciar'}
		</button>
		<button class="stop" onclick={stopSession} disabled={!isRunning || stopping}>
			{stopping ? 'PARANDO…' : 'PARAR'}
		</button>
	</div>

	<section class="live">
		<h2>Status</h2>
		{#if session === null}
			<p class="muted">Carregando…</p>
		{:else}
			<div class="status-row">
				<span class="badge badge-{session.status}">{session.status.toUpperCase()}</span>
				{#if session.stop_reason}
					<small>motivo: {session.stop_reason}</small>
				{/if}
				{#if session.game}
					<small>jogo: {session.game}</small>
				{/if}
				<small>ações: {session.actions_taken} / {maxActions}</small>
				<small>tempo: {fmtElapsed(elapsedSec)}</small>
			</div>

			{#if session.error}
				<p class="error">Erro: {session.error}</p>
			{/if}

			{#if session.last_screenshot_b64}
				<figure>
					<img
						src={`data:image/png;base64,${session.last_screenshot_b64}`}
						alt="Tela vista pela IA"
					/>
					<figcaption>O que a IA acabou de ver{session.region ? ' (recortado)' : ''}</figcaption>
				</figure>
			{/if}

			{#if session.last_action}
				<div class="action">
					<h3>Última ação</h3>
					<p>
						<strong>{session.last_action.kind}</strong>
						{#if session.last_action.key}
							<code>{session.last_action.key}</code>
						{/if}
						{#if session.last_action.x !== null && session.last_action.y !== null}
							<code>({session.last_action.x}, {session.last_action.y})</code>
						{/if}
					</p>
					{#if session.last_reason}
						<p class="reason">{session.last_reason}</p>
					{/if}
				</div>
			{/if}
		{/if}
	</section>
</main>

<style>
	.tabs {
		display: flex;
		gap: 0;
		max-width: 960px;
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

	.warning {
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

	main {
		max-width: 960px;
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

	h3 {
		margin: 0 0 0.25rem;
		font-size: 0.95rem;
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
		opacity: 0.75;
	}

	.row {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.row.limits {
		flex-direction: row;
		flex-wrap: wrap;
		gap: 0.75rem;
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
		min-width: 80px;
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

	.anti-cheat-block {
		margin-top: 0.5rem;
		padding: 0.75rem 1rem;
		background: #7f1d1d;
		color: #fef2f2;
		border-radius: 8px;
		line-height: 1.4;
		font-size: 0.9rem;
	}

	.anti-cheat-block strong {
		display: block;
		font-size: 0.95rem;
		margin-bottom: 0.4rem;
		letter-spacing: 0.04em;
	}

	.anti-cheat-block p {
		margin: 0;
		color: #fef2f2;
	}

	.anti-cheat-block code {
		background: #450a0a;
		color: #fecaca;
		padding: 0.05rem 0.35rem;
		border-radius: 4px;
		font-size: 0.8rem;
	}

	.controls {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		margin-top: 1rem;
	}

	button {
		font-size: 1rem;
		padding: 0.75rem 1.25rem;
		border-radius: 8px;
		border: 1px solid transparent;
		cursor: pointer;
		font-weight: 600;
		transition:
			background 120ms ease,
			transform 120ms ease;
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	button.start {
		background: #047857;
		color: white;
		border-color: #047857;
	}

	button.start:hover:not(:disabled) {
		background: #065f46;
	}

	button.stop {
		background: #b91c1c;
		color: white;
		border-color: #b91c1c;
		font-size: 1.1rem;
		padding: 0.85rem 1.75rem;
		letter-spacing: 0.05em;
	}

	button.stop:hover:not(:disabled) {
		background: #991b1b;
	}

	button.stop:not(:disabled) {
		animation: pulse 1.6s ease-in-out infinite;
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
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
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
	.badge-paused {
		background: #fef3c7;
		color: #92400e;
		border-color: #fde68a;
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

	.action {
		margin-top: 1rem;
		padding: 1rem 1.25rem;
		background: #f9fafb;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
	}

	.action p {
		margin: 0 0 0.25rem;
		line-height: 1.4;
	}

	.action code {
		background: #1f2937;
		color: white;
		padding: 0.1rem 0.4rem;
		border-radius: 4px;
		font-size: 0.85rem;
	}

	.reason {
		color: #6b7280;
		font-style: italic;
		font-size: 0.9rem;
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
</style>
