import type { PluginAPI } from '@ampcode/plugin'

export const description =
	'Adds the code_review tool: a read-only Astra reviewer using the shared project-management review prompt.'

const MODEL = 'openai/gpt-6-astra'
const REASONING_EFFORT = 'high'
const INSTRUCTIONS = ''

export default function (amp: PluginAPI) {
	const reviewer = amp.createAgent({
		name: 'Code review',
		model: MODEL,
		reasoningEffort: REASONING_EFFORT,
		instructions: INSTRUCTIONS,
		// Direct specialist calls hit Amp's retired subagent dispatcher; keep code-mode enabled.
		tools: {
			include: [
				'shell_command',
				'web_search',
				'read_web_page',
				'read_thread',
				'find_thread',
				'plugin__finder__finder',
				'plugin__librarian__librarian',
			],
		},
		display: { label: 'Code review', color: '#2563eb' },
	})

	amp.registerTool({
		name: 'code_review',
		title: 'Code review',
		description:
			'Review code changes with a read-only expert advisor. Include the diff or commit scope, intended behavior, relevant file paths, settled constraints, and what to ignore. Returns findings and recommended fixes; does not implement them. Use oracle for planning and other engineering advice.',
		inputSchema: {
			type: 'object',
			properties: {
				task: {
					type: 'string',
					description: 'The review scope, intended behavior, and constraints.',
				},
			},
			required: ['task'],
		},
		async execute(input, ctx) {
			const task = typeof input.task === 'string' ? input.task.trim() : ''
			if (!task) throw new Error('Missing code review task.')
			const thread = await reviewer.createThread({
				parentThreadID: ctx.thread.id,
			})
			const cancel = (): void => void thread.cancel()
			ctx.signal.addEventListener('abort', cancel, { once: true })
			try {
				await thread.appendUserMessage({
					type: 'user-message',
					content: `${task}\n\nParent thread: ${ctx.thread.id}`,
				})
				const reply = await thread.waitForResponse({
					timeoutMs: 30 * 60 * 1000,
				})
				return reply.content
					.flatMap((block) => (block.type === 'text' ? [block.text] : []))
					.join('')
			} finally {
				ctx.signal.removeEventListener('abort', cancel)
			}
		},
	})
}
