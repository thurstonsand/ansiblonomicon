import {
  array,
  boolean,
  decodeJson,
  defineApp,
  defineProvider,
  json,
  mutation,
  number,
  object,
  query,
  router,
  secrets,
  string,
  type Infer,
  type Schema,
} from "apps";
import { always } from "apps/operations/approval";

const HOST = "pod153-mcp.thurstons.house";
const BASE = `https://${HOST}`;

const beeper = defineProvider({
  name: "Beeper on pod153",
  hosts: [HOST],
  auth: {
    token: secrets({
      label: "Cloudflare Access service token and Beeper Desktop API token",
      fields: object({
        cf_access_client_id: string({ minLength: 1 }),
        cf_access_client_secret: string({ minLength: 1 }),
        beeper_token: string({ minLength: 1 }),
      }),
    }),
  },
  async health({ account, fetch, signal }) {
    await decodeJson(
      await fetch(`${BASE}/v1/accounts`, { headers: headersFor(account.fields), signal }),
      array(object({ accountID: string() })),
    );
  },
});

type Fields = { cf_access_client_id: string; cf_access_client_secret: string; beeper_token: string };

function headersFor(fields: Fields): Record<string, string> {
  return {
    "CF-Access-Client-Id": fields.cf_access_client_id,
    "CF-Access-Client-Secret": fields.cf_access_client_secret,
    Authorization: `Bearer ${fields.beeper_token}`,
  };
}

// Beeper Desktop names only the networks Beeper hosts; a self-hosted bridge has no name of its own.
const SELF_HOSTED_NETWORKS: Record<string, string> = { "sh-imsgbus": "iMessage" };

const Account = object({
  accountID: string(),
  network: string().optional(),
  bridge: object({ id: string() }),
});

const User = object({
  id: string(),
  fullName: string().optional(),
  phoneNumber: string().optional(),
  email: string().optional(),
  username: string().optional(),
  isSelf: boolean().optional(),
});

const Chat = object({
  id: string(),
  accountID: string(),
  title: string(),
  type: string(),
  participants: object({ items: array(User), total: number().optional() }),
  lastActivity: string().optional(),
  unreadCount: number(),
  isArchived: boolean().optional(),
  isMuted: boolean().optional(),
  isPinned: boolean().optional(),
  isLowPriority: boolean().optional(),
  isReadOnly: boolean().optional(),
  // A merged chat is one person's chats across networks; its members never appear in a search.
  merge: object({ chatIDs: array(string()) }).optional(),
});

const Attachment = object({
  type: string(),
  mimeType: string().optional(),
  fileName: string().optional(),
  duration: number().optional(),
  isVoiceNote: boolean().optional(),
  isSticker: boolean().optional(),
  isGif: boolean().optional(),
  transcription: object({ transcription: string() }).optional(),
});

const Message = object({
  id: string(),
  chatID: string(),
  senderID: string(),
  senderName: string().optional(),
  timestamp: string(),
  type: string().optional(),
  text: string().optional(),
  isSender: boolean().optional(),
  isHidden: boolean().optional(),
  isDeleted: boolean().optional(),
  isUnread: boolean().optional(),
  editedTimestamp: string().optional(),
  linkedMessageID: string().optional(),
  attachments: array(Attachment).optional(),
  reactions: array(object({ reactionKey: string(), participantID: string() })).optional(),
  links: array(object({ url: string(), title: string().optional() })).optional(),
});

// Cursors are null on an empty page, which string() refuses.
const Page = <T>(item: Schema<T, boolean>) =>
  object({ items: array(item), hasMore: boolean(), oldestCursor: json(), newestCursor: json() });

type ChatValue = Infer<typeof Chat>;
type MessageValue = Infer<typeof Message>;

function cursor(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

const CHAT_ID = "chat is a chat id from list_chats or search_messages.";

export default defineApp({ app: { accounts: { beeper } } }, async ({ app }) => {
  const headers = headersFor(app.accounts.beeper.fields);

  type Call = { fetch: typeof fetch; signal: AbortSignal };
  async function api<T>(call: Call, path: string, schema: Schema<T, boolean>, init?: { method: string; body?: unknown }) {
    const response = await call.fetch(`${BASE}${path}`, {
      method: init?.method ?? "GET",
      headers: init?.body === undefined ? headers : { ...headers, "Content-Type": "application/json" },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
      signal: call.signal,
    });
    return decodeJson(response, schema);
  }

  function path(...segments: string[]) {
    return segments.map(encodeURIComponent).join("/");
  }

  async function networks(call: Call) {
    const accounts = await api(call, "/v1/accounts", array(Account));
    return new Map(
      accounts.map((a) => [a.accountID, SELF_HOSTED_NETWORKS[a.bridge.id] ?? a.network ?? a.bridge.id]),
    );
  }

  async function accountIDs(call: Call, network: string) {
    const names = await networks(call);
    const ids = [...names].filter(([, name]) => name.toLowerCase() === network.toLowerCase()).map(([id]) => id);
    if (ids.length === 0) throw new Error(`No network named ${network}; networks: ${[...new Set(names.values())].join(", ")}`);
    return ids;
  }

  function person(user: Infer<typeof User>) {
    return {
      name: user.fullName ?? user.username ?? user.phoneNumber ?? user.email ?? user.id,
      ...(user.phoneNumber && { phone: user.phoneNumber }),
      ...(user.email && { email: user.email }),
      ...(user.username && { username: user.username }),
    };
  }

  function shapeChat(chat: ChatValue, names: Map<string, string>) {
    const others = chat.participants.items.filter((p) => !p.isSelf);
    return {
      id: chat.id,
      network: names.get(chat.accountID) ?? chat.accountID,
      title: chat.title,
      type: chat.type,
      ...(chat.type === "single" && others[0]
        ? { with: person(others[0]) }
        : {
            participants: others.map((p) => person(p).name),
            participant_count: chat.participants.total ?? chat.participants.items.length,
          }),
      last_activity: chat.lastActivity ?? null,
      unread: chat.unreadCount,
      ...(chat.isPinned && { pinned: true }),
      ...(chat.isMuted && { muted: true }),
      ...(chat.isLowPriority && { low_priority: true }),
      ...(chat.isArchived && { archived: true }),
      ...(chat.isReadOnly && { read_only: true }),
    };
  }

  // Beeper names only a chat's current participants, and gives anyone who has left as their Matrix id;
  // their Matrix profile still has their name.
  async function namesFor(call: Call, chats: readonly ChatValue[], messages: readonly MessageValue[]) {
    const names = new Map<string, string>(
      chats.flatMap((c) => c.participants.items.map((p) => [p.id, p.isSelf ? "me" : person(p).name] as const)),
    );
    const people = messages.flatMap((m) => [m.senderID, ...(m.reactions ?? []).map((r) => r.participantID)]);
    const unknown = [...new Set(people)].filter((id) => !names.has(id));
    await Promise.all(
      unknown.map(async (id) => {
        const response = await call.fetch(`${BASE}/_matrix/client/v3/profile/${encodeURIComponent(id)}`, {
          headers,
          signal: call.signal,
        });
        if (!response.ok) return;
        const profile = await decodeJson(response, object({ displayname: string().optional() }));
        if (profile.displayname) names.set(id, profile.displayname);
      }),
    );
    return names;
  }

  function shapeMessage(message: MessageValue, names: Map<string, string>) {
    return {
      id: message.id,
      from: message.isSender ? "me" : (names.get(message.senderID) ?? message.senderName ?? "unknown"),
      time: message.timestamp,
      ...(message.type && message.type !== "TEXT" && { type: message.type.toLowerCase() }),
      ...(message.text && { text: message.text }),
      ...(message.linkedMessageID && { reply_to: message.linkedMessageID }),
      ...(message.editedTimestamp && { edited: true }),
      ...(message.isDeleted && { deleted: true }),
      ...(message.isUnread && { unread: true }),
      ...(message.attachments?.length && {
        attachments: message.attachments.map((a, index) => ({
          index,
          kind: a.isVoiceNote ? "voice" : a.isSticker ? "sticker" : a.isGif ? "gif" : a.type,
          ...(a.fileName && { name: a.fileName }),
          ...(a.mimeType && { mime: a.mimeType }),
          ...(a.duration !== undefined && { seconds: a.duration }),
          ...(a.transcription && { transcription: a.transcription.transcription }),
        })),
      }),
      ...(message.reactions?.length && {
        reactions: message.reactions.map((r) => ({ emoji: r.reactionKey, by: names.get(r.participantID) ?? r.participantID })),
      }),
      ...(message.links?.length && {
        links: message.links.map((l) => ({ url: l.url, ...(l.title && { title: l.title }) })),
      }),
    };
  }

  // Tapbacks arrive as hidden events and show on the message they react to; membership changes
  // and other room notices carry no content type.
  function visible(message: MessageValue) {
    return !message.isHidden && message.type !== undefined;
  }

  async function chat(call: Call, id: string) {
    return api(call, `/v1/chats/${path(id)}`, Chat);
  }

  // A merged chat stands in for its members; list each member as the chat on its own network.
  async function expand(call: Call, chats: readonly ChatValue[]) {
    const expanded: ChatValue[] = [];
    for (const c of chats) {
      if (c.merge) expanded.push(...(await Promise.all(c.merge.chatIDs.map((id) => chat(call, id)))));
      else expanded.push(c);
    }
    return expanded;
  }

  // A page counts room notices too, so a chat's unread messages can reach back several pages.
  async function unreadMessages(call: Call, c: ChatValue) {
    const unread: MessageValue[] = [];
    let params = "";
    for (let pages = 0; pages < 5 && unread.length < c.unreadCount; pages++) {
      const page = await api(call, `/v1/chats/${path(c.id)}/messages${params}`, Page(Message));
      unread.push(...page.items.filter((m) => visible(m) && m.isUnread));
      const older = cursor(page.oldestCursor);
      if (!page.hasMore || !older) break;
      params = `?${new URLSearchParams({ cursor: older, direction: "before" })}`;
    }
    return unread.reverse();
  }

  const listChats = query(
    {
      description:
        "List chats across every network, newest activity first: iMessage, WhatsApp, Signal, Telegram, Google Chat, Google Voice, Facebook, Instagram, Beeper. " +
        "Each chat is one conversation on one network; the same person can have a chat on several networks. " +
        "Inputs (all optional): query finds chats by participant name, or by chat title with by_title true; network limits to one network by name; " +
        'type is "single" or "group"; unread_only lists only chats with unread messages and includes those messages; ' +
        "include_low_priority and include_archived add chats the inbox hides; limit (default 20, max 100); " +
        "older is the cursor from a previous page.",
      input: object({
        query: string().optional(),
        by_title: boolean().optional(),
        network: string().optional(),
        type: string().optional(),
        unread_only: boolean().optional(),
        include_low_priority: boolean().optional(),
        include_archived: boolean().optional(),
        limit: number().optional(),
        older: string().optional(),
      }),
    },
    async (call, input) => {
      const params = new URLSearchParams({ limit: String(Math.max(1, Math.min(input.limit ?? 20, 100))) });
      if (input.query) {
        params.set("query", input.query);
        params.set("scope", input.by_title ? "titles" : "participants");
      }
      if (input.type) params.set("type", input.type);
      if (input.unread_only) params.set("unreadOnly", "true");
      if (!input.include_low_priority && !input.include_archived && !input.query) params.set("inbox", "primary");
      if (input.older) {
        params.set("cursor", input.older);
        params.set("direction", "before");
      }
      if (input.network) for (const id of await accountIDs(call, input.network)) params.append("accountIDs", id);
      const [page, names] = await Promise.all([api(call, `/v1/chats/search?${params}`, Page(Chat)), networks(call)]);
      const chats = (await expand(call, page.items)).filter(
        (c) =>
          (!input.network || names.get(c.accountID)?.toLowerCase() === input.network.toLowerCase()) &&
          (!input.unread_only || c.unreadCount > 0) &&
          (input.include_archived || input.query || !c.isArchived) &&
          (input.include_low_priority || input.query || !c.isLowPriority),
      );
      const shaped = await Promise.all(
        chats.map(async (c) => {
          if (!input.unread_only) return shapeChat(c, names);
          const unread = await unreadMessages(call, c);
          const people = await namesFor(call, [c], unread);
          return { ...shapeChat(c, names), unread_messages: unread.map((m) => shapeMessage(m, people)) };
        }),
      );
      return { chats: shaped, older: page.hasMore ? cursor(page.oldestCursor) : null };
    },
  );

  const getMessages = query(
    {
      description:
        "Read a chat's messages, oldest to newest, with reactions, replies, attachments and transcriptions. " +
        `${CHAT_ID} Without a cursor, returns the latest messages; older is the "older" cursor from a previous call, ` +
        "to read further back.",
      input: object({ chat: string(), older: string().optional() }),
    },
    async (call, input) => {
      const params = new URLSearchParams();
      if (input.older) {
        params.set("cursor", input.older);
        params.set("direction", "before");
      }
      const [c, page, names] = await Promise.all([
        chat(call, input.chat),
        api(call, `/v1/chats/${path(input.chat)}/messages?${params}`, Page(Message)),
        networks(call),
      ]);
      const messages = page.items.filter(visible).reverse();
      const people = await namesFor(call, [c], messages);
      return {
        chat: shapeChat(c, names),
        messages: messages.map((m) => shapeMessage(m, people)),
        older: page.hasMore ? cursor(page.oldestCursor) : null,
      };
    },
  );

  const searchMessages = query(
    {
      description:
        "Search messages across every chat, newest first. Inputs (all optional): query matches all its words literally, so use the words the person would have written; " +
        'chat limits to one chat id; network limits to one network by name; from is "me" or "others"; ' +
        'after and before are ISO 8601 times; media is a list such as ["image"], ["video"], ["link"], ["file"] or ["any"]; ' +
        "limit (default and max 20); older is the cursor from a previous page.",
      input: object({
        query: string().optional(),
        chat: string().optional(),
        network: string().optional(),
        from: string().optional(),
        after: string().optional(),
        before: string().optional(),
        media: array(string()).optional(),
        limit: number().optional(),
        older: string().optional(),
      }),
    },
    async (call, input) => {
      const params = new URLSearchParams({
        limit: String(Math.max(1, Math.min(input.limit ?? 20, 20))),
        excludeLowPriority: "false",
      });
      if (input.query) params.set("query", input.query);
      if (input.chat) params.append("chatIDs", input.chat);
      if (input.network) for (const id of await accountIDs(call, input.network)) params.append("accountIDs", id);
      if (input.from) params.set("sender", input.from);
      if (input.after) params.set("dateAfter", input.after);
      if (input.before) params.set("dateBefore", input.before);
      for (const m of input.media ?? []) params.append("mediaTypes", m);
      if (input.older) {
        params.set("cursor", input.older);
        params.set("direction", "before");
      }
      const [page, names] = await Promise.all([
        api(call, `/v1/messages/search?${params}`, object({ ...Page(Message).fields, chats: json() })),
        networks(call),
      ]);
      const chats = new Map<string, ChatValue>();
      for (const [id, raw] of Object.entries(page.chats as Record<string, unknown>)) chats.set(id, Chat.parse(raw));
      const messages = page.items.filter(visible);
      const people = await namesFor(call, [...chats.values()], messages);
      return {
        messages: messages.map((m) => {
          const c = chats.get(m.chatID);
          return { chat: c ? shapeChat(c, names) : { id: m.chatID }, ...shapeMessage(m, people) };
        }),
        older: page.hasMore ? cursor(page.oldestCursor) : null,
      };
    },
  );

  const getImage = query(
    {
      description:
        "Get an image from a message as a URL, scaled to at most 1568 px and stripped of metadata, valid for ten minutes. " +
        "Open the URL with an image viewing tool to see it. For a video, returns its preview frame when the network sent one. " +
        `${CHAT_ID} message is its id; index picks one of the message's attachments (default 0).`,
      input: object({ chat: string(), message: string(), index: number().optional() }),
    },
    async (call, input) =>
      api(
        call,
        "/beeper/images",
        object({ url: string(), width: number(), height: number(), expires_at: string() }),
        { method: "POST", body: { chat: input.chat, message: input.message, index: input.index ?? 0 } },
      ),
  );

  const sent = object({ chatID: string(), pendingMessageID: string() });

  const sendMessage = mutation(
    {
      description:
        `Send a text message. ${CHAT_ID} text accepts Markdown on networks with formatting. ` +
        "reply_to is a message id to reply to. Sends exactly where chat says; it never picks another network.",
      input: object({ chat: string(), text: string({ minLength: 1 }), reply_to: string().optional() }),
      approval: always(),
    },
    async (call, input) => {
      const result = await api(call, `/v1/chats/${path(input.chat)}/messages`, sent, {
        method: "POST",
        body: { text: input.text, ...(input.reply_to && { replyToMessageID: input.reply_to }) },
      });
      return { chat: result.chatID, message: result.pendingMessageID };
    },
  );

  const react = mutation(
    {
      description: `React to a message with an emoji, or take your reaction back with remove. ${CHAT_ID} message is its id.`,
      input: object({ chat: string(), message: string(), emoji: string({ minLength: 1 }), remove: boolean().optional() }),
      approval: always(),
    },
    async (call, input) => {
      const reactions = `/v1/chats/${path(input.chat, "messages", input.message, "reactions")}`;
      if (input.remove) {
        await call.fetch(`${BASE}${reactions}/${encodeURIComponent(input.emoji)}`, { method: "DELETE", headers, signal: call.signal }).then(ok);
      } else {
        await api(call, reactions, object({ success: boolean() }), { method: "POST", body: { reactionKey: input.emoji } });
      }
      return { ok: true };
    },
  );

  const editMessage = mutation(
    {
      description: `Replace the text of a message you sent. ${CHAT_ID} message is its id. Networks allow edits only for a while after sending.`,
      input: object({ chat: string(), message: string(), text: string({ minLength: 1 }) }),
      approval: always(),
    },
    async (call, input) => {
      await api(call, `/v1/chats/${path(input.chat, "messages", input.message)}`, object({ id: string() }), {
        method: "PUT",
        body: { text: input.text },
      });
      return { ok: true };
    },
  );

  const deleteMessage = mutation(
    {
      description: `Unsend a message you sent, for everyone. ${CHAT_ID} message is its id. Networks allow this only for a while after sending.`,
      input: object({ chat: string(), message: string() }),
      approval: always(),
    },
    async (call, input) => {
      await call
        .fetch(`${BASE}/v1/chats/${path(input.chat, "messages", input.message)}`, { method: "DELETE", headers, signal: call.signal })
        .then(ok);
      return { ok: true };
    },
  );

  const markRead = mutation(
    {
      description: `Mark a chat read, which the other people in it may see. ${CHAT_ID}`,
      input: object({ chat: string() }),
      approval: always(),
    },
    async (call, input) => {
      await api(call, `/v1/chats/${path(input.chat)}/read`, object({ id: string() }), { method: "POST", body: {} });
      return { ok: true };
    },
  );

  return {
    tools: router(
      {
        list_chats: listChats,
        get_messages: getMessages,
        search_messages: searchMessages,
        get_image: getImage,
        send_message: sendMessage,
        react,
        edit_message: editMessage,
        delete_message: deleteMessage,
        mark_read: markRead,
      },
      {
        title: "Beeper",
        description: "Read, search and send messages on every network Thurston uses, through Beeper.",
        instructions: INSTRUCTIONS,
      },
    ),
  };
});

async function ok(response: Response) {
  if (!response.ok) throw new Error(`Beeper answered ${response.status}: ${await response.text()}`);
}

const INSTRUCTIONS = `
These tools are Thurston's messages on every network, through Beeper. Every chat tool takes a chat id, and a chat is one conversation on one network.

Finding a chat
- For a person, call list_chats with query set to their name. One person often has a chat on several networks, such as iMessage and WhatsApp; each comes back as its own chat with its network.
- For a group by its name, use list_chats with query and by_title true. Add type "single" or "group" to narrow.
- When the person's name matches several people, ask which one rather than guessing.

Choosing where to reply
- Replying to a particular message: send in that message's chat, with reply_to when quoting it helps.
- Otherwise, write in the chat with that person that has the most recent activity. Do not switch networks unless asked.

Reading
- What's new: list_chats with unread_only true returns each unread chat with its unread messages, so a separate read is rarely needed.
- A chat's last_activity can be newer than its newest message: a reaction counts as activity and shows on the message it reacts to, under reactions.
- get_messages returns the latest page; pass its older cursor to read further back.
- search_messages finds words across all chats; filter with chat, network, from, after and before.
- Attachments list an index; pass it to get_image to see an image. Voice notes carry a transcription when one exists.

Sending
- send_message, react, edit_message, delete_message and mark_read each ask Thurston to approve. Say what you will send and where before calling.
- Edits and unsends work only for a short while after sending, and not on every network.
`.trim();
