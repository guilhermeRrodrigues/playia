<script lang="ts">
	import { onMount } from 'svelte';
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

	const TEMPOS: Tempo[] = ['turn_based', 'slow_realtime', 'fast_realtime'];
	const ANTI_CHEATS: AntiCheat[] = [
		'none',
		'unknown',
		'hyperion',
		'eac',
		'battleye',
		'vanguard',
		'other'
	];

	const tempoLabel: Record<Tempo, string> = {
		turn_based: 'Turn-based',
		slow_realtime: 'Slow realtime',
		fast_realtime: 'Fast realtime'
	};

	const antiCheatLabel: Record<AntiCheat, string> = {
		none: 'Nenhum',
		unknown: 'Desconhecido',
		hyperion: 'Hyperion (Roblox)',
		eac: 'EAC',
		battleye: 'BattlEye',
		vanguard: 'Vanguard',
		other: 'Outro'
	};

	let games = $state<Game[]>([]);
	let selectedId = $state<string | null>(null);
	let selected = $derived(games.find((g) => g.id === selectedId) ?? null);
	let filterTempo = $state<Tempo | ''>('');
	let filterAntiCheat = $state<AntiCheat | ''>('');
	let error = $state('');
	let loading = $state(true);

	let showForm = $state(false);
	let editingId = $state<string | null>(null); // null = criando

	// campos do formulário (compartilhados entre criar/editar)
	let formId = $state('');
	let formName = $state('');
	let formUrl = $state('');
	let formTempo = $state<Tempo>('turn_based');
	let formAntiCheat = $state<AntiCheat>('none');
	let formAllowedKeysCsv = $state('');
	let formGoal = $state('');
	let formNotes = $state('');

	let formError = $state('');

	onMount(loadGames);

	async function loadGames() {
		error = '';
		loading = true;
		try {
			const url = new URL(`${BACKEND}/games`);
			if (filterTempo) url.searchParams.set('tempo', filterTempo);
			if (filterAntiCheat) url.searchParams.set('anti_cheat', filterAntiCheat);
			const res = await fetch(url);
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			games = (await res.json()) as Game[];
			if (selectedId !== null && !games.find((g) => g.id === selectedId)) {
				selectedId = null;
			}
		} catch (e) {
			error = humanizeException(e);
		} finally {
			loading = false;
		}
	}

	function openNew() {
		editingId = null;
		formId = '';
		formName = '';
		formUrl = '';
		formTempo = 'turn_based';
		formAntiCheat = 'none';
		formAllowedKeysCsv = '';
		formGoal = '';
		formNotes = '';
		formError = '';
		showForm = true;
	}

	function openEdit(g: Game) {
		editingId = g.id;
		formId = g.id;
		formName = g.name;
		formUrl = g.url;
		formTempo = g.tempo;
		formAntiCheat = g.anti_cheat;
		formAllowedKeysCsv = g.allowed_keys.join(', ');
		formGoal = g.goal;
		formNotes = g.notes ?? '';
		formError = '';
		showForm = true;
	}

	function closeForm() {
		showForm = false;
		formError = '';
	}

	function parseKeys(csv: string): string[] {
		return csv
			.split(',')
			.map((s) => s.trim())
			.filter((s) => s.length > 0);
	}

	async function submitForm(e: Event) {
		e.preventDefault();
		formError = '';
		const payload = {
			name: formName,
			url: formUrl,
			tempo: formTempo,
			anti_cheat: formAntiCheat,
			allowed_keys: parseKeys(formAllowedKeysCsv),
			goal: formGoal,
			notes: formNotes.trim() ? formNotes : null
		};
		try {
			const res =
				editingId === null
					? await fetch(`${BACKEND}/games`, {
							method: 'POST',
							headers: { 'Content-Type': 'application/json' },
							body: JSON.stringify({ id: formId, ...payload })
						})
					: await fetch(`${BACKEND}/games/${editingId}`, {
							method: 'PUT',
							headers: { 'Content-Type': 'application/json' },
							body: JSON.stringify(payload)
						});
			if (!res.ok) {
				formError = humanizeError(res.status, await res.text());
				return;
			}
			showForm = false;
			const targetId = editingId ?? formId;
			await loadGames();
			selectedId = targetId;
		} catch (err) {
			formError = humanizeException(err);
		}
	}

	async function deleteGame(g: Game) {
		const ok = confirm(
			`Apagar o jogo "${g.name}" (${g.id})?\n\n` +
				`Gravações ou motor models associados bloqueiam o delete (409).`
		);
		if (!ok) return;
		error = '';
		try {
			const res = await fetch(`${BACKEND}/games/${g.id}`, { method: 'DELETE' });
			if (!res.ok) {
				error = humanizeError(res.status, await res.text());
				return;
			}
			if (selectedId === g.id) selectedId = null;
			await loadGames();
		} catch (e) {
			error = humanizeException(e);
		}
	}
</script>

<main>
	<header>
		<h1>Jogos</h1>
		<p class="subtitle">
			Catálogo persistente. Cada jogo tem <em>tempo</em> (turn-based / slow / fast)
			e flag de <em>anti-cheat</em>. Sessões em jogos com anti-cheat ≠ <code>none</code>
			ficam bloqueadas por padrão.
		</p>
	</header>

	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}

	<section class="toolbar">
		<div class="filters">
			<label>
				<span>Tempo</span>
				<select bind:value={filterTempo} onchange={loadGames}>
					<option value="">Qualquer</option>
					{#each TEMPOS as t (t)}
						<option value={t}>{tempoLabel[t]}</option>
					{/each}
				</select>
			</label>
			<label>
				<span>Anti-cheat</span>
				<select bind:value={filterAntiCheat} onchange={loadGames}>
					<option value="">Qualquer</option>
					{#each ANTI_CHEATS as ac (ac)}
						<option value={ac}>{antiCheatLabel[ac]}</option>
					{/each}
				</select>
			</label>
		</div>
		<button class="primary" onclick={openNew}>+ Novo jogo</button>
	</section>

	<section class="layout">
		<div class="list">
			{#if loading}
				<p class="muted">Carregando…</p>
			{:else if games.length === 0}
				<p class="muted">Nenhum jogo casa com os filtros.</p>
			{:else}
				<table>
					<thead>
						<tr>
							<th>Nome</th>
							<th>Tempo</th>
							<th>Anti-cheat</th>
							<th>URL</th>
							<th>Ações</th>
						</tr>
					</thead>
					<tbody>
						{#each games as g (g.id)}
							<tr
								class:selected={selectedId === g.id}
								onclick={() => (selectedId = g.id)}
							>
								<td>
									<strong>{g.name}</strong><br />
									<small><code>{g.id}</code></small>
								</td>
								<td>{tempoLabel[g.tempo]}</td>
								<td>
									<span class="badge badge-ac-{g.anti_cheat}">
										{antiCheatLabel[g.anti_cheat]}
									</span>
								</td>
								<td>
									<a href={g.url} target="_blank" rel="noreferrer">{g.url}</a>
								</td>
								<td class="actions">
									<button
										class="ghost"
										onclick={(e) => {
											e.stopPropagation();
											openEdit(g);
										}}>Editar</button
									>
									<button
										class="danger"
										onclick={(e) => {
											e.stopPropagation();
											deleteGame(g);
										}}>Apagar</button
									>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</div>

		<aside class="detail">
			{#if selected}
				<h2>{selected.name}</h2>
				<p><strong>ID:</strong> <code>{selected.id}</code></p>
				<p><strong>URL:</strong> <a href={selected.url} target="_blank" rel="noreferrer">{selected.url}</a></p>
				<p><strong>Tempo:</strong> {tempoLabel[selected.tempo]}</p>
				<p>
					<strong>Anti-cheat:</strong>
					<span class="badge badge-ac-{selected.anti_cheat}">
						{antiCheatLabel[selected.anti_cheat]}
					</span>
				</p>
				<p>
					<strong>Teclas permitidas:</strong>
					{#if selected.allowed_keys.length === 0}
						<em>(nenhuma)</em>
					{:else}
						{#each selected.allowed_keys as k (k)}
							<code class="key">{k}</code>
						{/each}
					{/if}
				</p>
				<div class="goal">
					<strong>Objetivo:</strong>
					<p>{selected.goal}</p>
				</div>

				{#if selected.notes}
					<div class="notes">
						<strong>Notas:</strong>
						<p>{selected.notes}</p>
					</div>
				{/if}

				{#if selected.anti_cheat !== 'none'}
					<div class="anti-cheat-warning" role="alert">
						<strong>⚠ AVISO DE BAN</strong>
						<p>
							Este jogo usa <strong>{antiCheatLabel[selected.anti_cheat]}</strong>.
							Automação detectada = ban da conta (e possivelmente do HWID).
							Sessões só são liberadas via API enviando
							<code>acknowledge_ban_risk: "estou ciente do risco"</code>
							no corpo do <code>/session/start</code>.
						</p>
						{#if selected.anti_cheat === 'hyperion'}
							<p>
								Para dev seguro: rode o jogo em Roblox Studio <em>Play Solo</em>
								(não conecta no servidor; Hyperion não roda nesse modo).
							</p>
						{/if}
					</div>
				{/if}
			{:else}
				<p class="muted">Selecione um jogo na lista para ver detalhes.</p>
			{/if}
		</aside>
	</section>

	{#if showForm}
		<div
			class="modal-backdrop"
			onclick={closeForm}
			onkeydown={(e) => e.key === 'Escape' && closeForm()}
			role="presentation"
		>
			<div
				class="modal"
				onclick={(e) => e.stopPropagation()}
				onkeydown={(e) => e.stopPropagation()}
				role="dialog"
				tabindex="-1"
				aria-modal="true"
				aria-label={editingId === null ? 'Novo jogo' : `Editar ${editingId}`}
			>
				<h3>{editingId === null ? 'Novo jogo' : `Editar ${editingId}`}</h3>
				<form onsubmit={submitForm}>
					{#if editingId === null}
						<label>
							<span>ID (slug, kebab-case)</span>
							<input
								type="text"
								bind:value={formId}
								required
								pattern="^[a-z0-9][a-z0-9-]*$"
								placeholder="ex: chrome-dino"
							/>
						</label>
					{/if}
					<label>
						<span>Nome</span>
						<input type="text" bind:value={formName} required />
					</label>
					<label>
						<span>URL</span>
						<input type="text" bind:value={formUrl} required placeholder="https://… ou chrome://dino" />
					</label>
					<div class="form-row">
						<label>
							<span>Tempo</span>
							<select bind:value={formTempo} required>
								{#each TEMPOS as t (t)}
									<option value={t}>{tempoLabel[t]}</option>
								{/each}
							</select>
						</label>
						<label>
							<span>Anti-cheat</span>
							<select bind:value={formAntiCheat} required>
								{#each ANTI_CHEATS as ac (ac)}
									<option value={ac}>{antiCheatLabel[ac]}</option>
								{/each}
							</select>
						</label>
					</div>
					<label>
						<span>Teclas permitidas (CSV)</span>
						<input
							type="text"
							bind:value={formAllowedKeysCsv}
							placeholder="ArrowUp, ArrowDown, Space"
						/>
					</label>
					<label>
						<span>Objetivo (prompt da IA)</span>
						<textarea bind:value={formGoal} rows="3" required></textarea>
					</label>
					<label>
						<span>Notas (opcional)</span>
						<textarea bind:value={formNotes} rows="2"></textarea>
					</label>

					{#if formError}
						<p class="error">{formError}</p>
					{/if}

					<div class="form-actions">
						<button type="button" class="ghost" onclick={closeForm}>Cancelar</button>
						<button type="submit" class="primary">
							{editingId === null ? 'Criar' : 'Salvar'}
						</button>
					</div>
				</form>
			</div>
		</div>
	{/if}
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
		font-size: 1.25rem;
	}

	h3 {
		margin: 0 0 0.75rem;
		font-size: 1.1rem;
	}

	.subtitle {
		margin: 0;
		color: #6b7280;
		line-height: 1.4;
	}

	.toolbar {
		display: flex;
		align-items: flex-end;
		gap: 1rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}

	.filters {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.filters label,
	.modal label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.85rem;
		color: #374151;
	}

	.layout {
		display: grid;
		grid-template-columns: 2fr 1fr;
		gap: 1.25rem;
	}

	@media (max-width: 800px) {
		.layout {
			grid-template-columns: 1fr;
		}
	}

	.list {
		overflow-x: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
		background: #fff;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
		overflow: hidden;
	}

	th,
	td {
		text-align: left;
		padding: 0.6rem 0.8rem;
		border-bottom: 1px solid #f3f4f6;
		vertical-align: top;
	}

	th {
		background: #f9fafb;
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: #6b7280;
	}

	tbody tr {
		cursor: pointer;
		transition: background 80ms ease;
	}

	tbody tr:hover {
		background: #f9fafb;
	}

	tbody tr.selected {
		background: #eff6ff;
	}

	td.actions {
		display: flex;
		gap: 0.4rem;
	}

	td code,
	.detail code {
		background: #1f2937;
		color: #f9fafb;
		padding: 0.1rem 0.4rem;
		border-radius: 4px;
		font-size: 0.8rem;
	}

	code.key {
		margin-right: 0.25rem;
	}

	.badge {
		display: inline-block;
		padding: 0.1rem 0.5rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 600;
		border: 1px solid transparent;
	}

	.badge-ac-none {
		background: #ecfdf5;
		color: #065f46;
		border-color: #6ee7b7;
	}

	.badge-ac-unknown {
		background: #f3f4f6;
		color: #4b5563;
		border-color: #d1d5db;
	}

	.badge-ac-hyperion,
	.badge-ac-eac,
	.badge-ac-battleye,
	.badge-ac-vanguard,
	.badge-ac-other {
		background: #fee2e2;
		color: #991b1b;
		border-color: #fca5a5;
	}

	button {
		padding: 0.45rem 0.85rem;
		border-radius: 6px;
		border: 1px solid transparent;
		font-size: 0.9rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 120ms ease;
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	button.primary {
		background: #047857;
		color: white;
		border-color: #047857;
	}

	button.primary:hover {
		background: #065f46;
	}

	button.ghost {
		background: white;
		color: #1f2937;
		border-color: #d1d5db;
	}

	button.ghost:hover {
		background: #f3f4f6;
	}

	button.danger {
		background: #fef2f2;
		color: #991b1b;
		border-color: #fca5a5;
	}

	button.danger:hover {
		background: #fee2e2;
	}

	.detail {
		padding: 1rem 1.25rem;
		background: #f9fafb;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
		font-size: 0.9rem;
		line-height: 1.4;
		min-height: 240px;
	}

	.detail p {
		margin: 0.3rem 0;
	}

	.detail .goal,
	.detail .notes {
		margin-top: 0.75rem;
	}

	.detail .goal p,
	.detail .notes p {
		margin-top: 0.25rem;
		white-space: pre-wrap;
	}

	.anti-cheat-warning {
		margin-top: 1rem;
		padding: 0.75rem 1rem;
		background: #7f1d1d;
		color: #fef2f2;
		border-radius: 8px;
		line-height: 1.4;
	}

	.anti-cheat-warning strong {
		display: block;
		font-size: 1rem;
		margin-bottom: 0.4rem;
		letter-spacing: 0.04em;
	}

	.anti-cheat-warning p {
		margin: 0.4rem 0;
		color: #fef2f2;
	}

	.anti-cheat-warning code {
		background: #450a0a;
		color: #fecaca;
	}

	.muted {
		color: #9ca3af;
		font-style: italic;
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

	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(31, 41, 55, 0.55);
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding: 4rem 1rem;
		z-index: 50;
	}

	.modal {
		background: white;
		border-radius: 10px;
		padding: 1.5rem;
		width: min(560px, 100%);
		max-height: 80vh;
		overflow-y: auto;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
	}

	.modal form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.modal label span {
		font-weight: 600;
		color: #374151;
	}

	.modal input,
	.modal select,
	.modal textarea {
		padding: 0.4rem 0.5rem;
		border: 1px solid #d1d5db;
		border-radius: 6px;
		font-size: 0.95rem;
		background: white;
		font-family: inherit;
	}

	.modal textarea {
		resize: vertical;
	}

	.form-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}

	.form-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}

	a {
		color: #1d4ed8;
		text-decoration: none;
	}

	a:hover {
		text-decoration: underline;
	}
</style>
