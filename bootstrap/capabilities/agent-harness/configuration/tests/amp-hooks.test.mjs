import assert from 'node:assert/strict'
import { test } from 'node:test'
import codeReview from '../../amp-plugins/code-review.ts'
import timing from '../../amp-plugins/command-timing.ts'
import comments from '../../amp-plugins/no-chat-comments.ts'

function register(extension) {
	const handlers = {}
	extension({
		on: (event, handler) => {
			handlers[event] = handler
		},
		helpers: {
			shellCommandFromToolCall: (event) =>
				event.tool === 'shell_command'
					? { command: event.input.command }
					: null,
		},
	})
	return handlers
}

test('Amp times foreground commands, preserves failures, and separates overlapping threads', (t) => {
	let now = 0
	t.mock.method(performance, 'now', () => now)
	const hooks = register(timing)
	for (const [duration, severity] of [
		[60000, 'none'],
		[60001, 'slow'],
		[300000, 'slow'],
		[300001, 'very slow'],
	]) {
		now = 0
		const call = {
			thread: { id: 'one' },
			toolUseID: 'same-id',
			tool: 'shell_command',
			input: { command: 'false' },
		}
		hooks['tool.call'](call)
		now = 500
		hooks['tool.call']({ ...call, thread: { id: 'two' } })
		now = duration
		const result = hooks['tool.result']({
			...call,
			status: 'error',
			error: 'failed',
			output: { output: 'original', exitCode: 7 },
		})
		assert.equal(result.status, 'error')
		assert.equal(result.error, 'failed')
		assert.equal(result.output.output, 'original')
		assert.equal(result.output.exitCode, 7)
		assert.equal(
			result.output.commandTiming.includes('Slow feedback loop:'),
			severity === 'slow',
		)
		assert.equal(
			result.output.commandTiming.includes('Very slow feedback loop:'),
			severity === 'very slow',
		)
		assert.equal(hooks['tool.result']({ ...call, status: 'done' }), undefined)
	}
})

test('Amp follows a background process through polls without timing each poll as a command', (t) => {
	let now = 0
	t.mock.method(performance, 'now', () => now)
	const hooks = register(timing)
	const call = {
		thread: { id: 'one' },
		toolUseID: 'launch',
		tool: 'shell_command',
		input: { command: 'sleep 120' },
	}
	hooks['tool.call'](call)
	now = 1000
	const running = hooks['tool.result']({
		...call,
		status: 'done',
		output: { running: true, pid: 123, output: '' },
	})
	assert.match(running.output.commandTiming, /elapsed so far: 1.0s/)
	const poll = {
		thread: call.thread,
		toolUseID: 'poll',
		tool: 'shell_command_status',
		input: { pid: 123 },
		status: 'done',
	}
	now = 61000
	assert.match(
		hooks['tool.result']({ ...poll, output: { running: true, pid: 123 } })
			.output.commandTiming,
		/elapsed so far: 61.0s/,
	)
	now = 125000
	const finished = hooks['tool.result']({
		...poll,
		output: { running: false, output: 'finished', exitCode: 0 },
	})
	assert.match(finished.output.commandTiming, /Shell elapsed: 125.0s/)
	assert.equal(finished.output.output, 'finished')
	assert.equal(
		hooks['tool.result']({ ...poll, output: { running: false } }),
		undefined,
	)
})

test('Amp rejects new chat-history comments in patches and edits, not context or strings', async () => {
	const hooks = register(comments)
	for (const [text, blocked] of [
		['// as requested', true],
		['# Used to be x; now y', true],
		['// The server requires a stable ID.', false],
		['value = "# as requested"', false],
	]) {
		for (const [tool, input] of [
			[
				'apply_patch',
				{
					patchText: `*** Begin Patch\n*** Add File: a.py\n+${text}\n*** End Patch`,
				},
			],
			['edit_file', { old_str: 'old', new_str: text }],
		]) {
			const result = await hooks['tool.call']({ tool, input })
			assert.equal(result.action, blocked ? 'reject-and-continue' : 'allow')
		}
	}
	assert.equal(
		(
			await hooks['tool.call']({
				tool: 'apply_patch',
				input: {
					patchText:
						'*** Begin Patch\n*** Update File: a.py\n@@\n # as requested\n-old\n+new\n*** End Patch',
				},
			})
		).action,
		'allow',
	)
})

function registerReview(thread) {
	let tool
	codeReview({
		createAgent: () => ({
			createThread: async (options) => {
				thread.options = options
				return thread
			},
		}),
		registerTool: (definition) => {
			tool = definition
		},
	})
	return tool
}

test('Amp review forwards scope and parent context and returns only report text', async () => {
	const messages = []
	let cancelled = false
	const thread = {
		appendUserMessage: async (message) => messages.push(message),
		waitForResponse: async () => ({
			content: [
				{ type: 'text', text: 'One blocker: ' },
				{ type: 'image', url: 'ignored' },
				{ type: 'text', text: 'a stale cache.' },
			],
		}),
		cancel: async () => {
			cancelled = true
		},
	}
	const tool = registerReview(thread)
	const controller = new AbortController()
	const ctx = { thread: { id: 'parent-review' }, signal: controller.signal }
	assert.equal(
		await tool.execute({ task: '  Review only src/cache.ts.  ' }, ctx),
		'One blocker: a stale cache.',
	)
	assert.deepEqual(thread.options, { parentThreadID: 'parent-review' })
	assert.deepEqual(messages, [
		{
			type: 'user-message',
			content: 'Review only src/cache.ts.\n\nParent thread: parent-review',
		},
	])
	controller.abort()
	assert.equal(cancelled, false)
	await assert.rejects(
		tool.execute({ task: '   ' }, ctx),
		/Missing code review task/,
	)
})

test('Amp review cancels an in-flight child and propagates its error', async () => {
	const waiting = Promise.withResolvers()
	const report = Promise.withResolvers()
	const tool = registerReview({
		appendUserMessage: async () => {},
		waitForResponse: () => {
			waiting.resolve()
			return report.promise
		},
		cancel: async () => report.reject(new Error('Child cancelled')),
	})
	const controller = new AbortController()
	const execution = tool.execute(
		{ task: 'Review src/cache.ts.' },
		{ thread: { id: 'parent-review' }, signal: controller.signal },
	)
	await waiting.promise
	controller.abort()
	await assert.rejects(execution, /Child cancelled/)
})
