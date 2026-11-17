import type { PluginAPI, ThreadID } from '@ampcode/plugin'

export const description =
	'Warns the agent when shell execution, excluding approval waits, runs over 60 seconds, and more strongly over 5 minutes.'

interface Call {
	started: number
	approvalWait: number
}

interface Timings {
	calls: Map<string, Call>
	processes: Map<number, number>
}

export default function commandTiming(amp: PluginAPI) {
	const threads = new Map<string, Timings>()

	function track(threadID: ThreadID) {
		const timings: Timings = { calls: new Map(), processes: new Map() }
		threads.set(threadID, timings)
		let approvalStarted: number | undefined
		amp.threads.get(threadID).state.subscribe((state) => {
			if (state === 'awaiting-approval') {
				approvalStarted ??= performance.now()
			} else if (approvalStarted !== undefined) {
				const wait = performance.now() - approvalStarted
				approvalStarted = undefined
				for (const call of timings.calls.values()) call.approvalWait += wait
			}
		})
		return timings
	}

	amp.on('tool.call', (event) => {
		if (amp.helpers.shellCommandFromToolCall(event)) {
			const timings = threads.get(event.thread.id) ?? track(event.thread.id)
			timings.calls.set(event.toolUseID, {
				started: performance.now(),
				approvalWait: 0,
			})
		}
		return { action: 'allow' }
	})

	amp.on('tool.result', (event) => {
		const timings = threads.get(event.thread.id)
		if (!timings) return
		const polling =
			event.tool === 'shell_command_status' ||
			event.tool === 'shell_command_kill'
		const call = timings.calls.get(event.toolUseID)
		timings.calls.delete(event.toolUseID)
		const started =
			polling && typeof event.input.pid === 'number'
				? timings.processes.get(event.input.pid)
				: call && call.started + call.approvalWait
		if (started === undefined) return
		const seconds = (performance.now() - started) / 1000
		const output = event.output
		const object =
			output !== null && typeof output === 'object' && !Array.isArray(output)
				? (output as Record<string, unknown>)
				: undefined
		const running = object?.running === true
		if (running && typeof object?.pid === 'number') {
			timings.processes.set(object.pid, started)
		} else if (polling && typeof event.input.pid === 'number') {
			// A failed poll does not tell us whether the process finished.
			if (event.status === 'done' && object?.running === false) {
				timings.processes.delete(event.input.pid)
			} else {
				return
			}
		}
		if (seconds <= 60) return
		let message = `[command-timing] Shell execution${running ? ' so far' : ''}: ${seconds.toFixed(1)}s.`
		message +=
			seconds > 300
				? ' Very slow feedback loop: over 5 minutes. Change the iteration strategy before repeating this command.'
				: ' Slow feedback loop: over 60 seconds.'
		message +=
			" Find a narrower test, file, or reproduction for the next edit. Keep required full-suite validation for the final check; don't skip verification."
		return {
			status: event.status,
			...(event.status !== 'done' ? { error: event.error } : {}),
			output: object
				? { ...object, commandTiming: message }
				: Array.isArray(output)
					? [...output, { type: 'text', text: message }]
					: `${output ?? ''}\n\n${message}`,
		}
	})
}
