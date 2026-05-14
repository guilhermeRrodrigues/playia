<script lang="ts">
	import { page } from '$app/state';
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<nav>
	<a href="/" class:active={page.url.pathname === '/'}>PlayIA</a>
	<a href="/play" class:active={page.url.pathname.startsWith('/play')}>Play</a>
	<a href="/inspect" class:active={page.url.pathname.startsWith('/inspect')}>Inspect</a>
</nav>

{@render children()}

<style>
	nav {
		display: flex;
		gap: 1rem;
		align-items: center;
		padding: 0.75rem 1.5rem;
		border-bottom: 1px solid #e5e7eb;
		background: #fafafa;
		font-family:
			ui-sans-serif,
			system-ui,
			-apple-system,
			'Segoe UI',
			sans-serif;
		font-size: 0.9rem;
	}

	nav a {
		color: #4b5563;
		text-decoration: none;
		padding: 0.25rem 0.5rem;
		border-radius: 6px;
	}

	nav a:hover {
		background: #f3f4f6;
		color: #1f2937;
	}

	nav a.active {
		background: #1f2937;
		color: white;
	}

	nav a:first-child {
		font-weight: 600;
		color: #1f2937;
	}

	nav a:first-child.active {
		color: white;
	}
</style>
