extern fn open(path: [*:0]const u8, flags: c_int, mode: c_int) c_int;
extern fn read(fd: c_int, buf: [*]u8, count: usize) isize;
extern fn write(fd: c_int, buf: [*]const u8, count: usize) isize;
extern fn close(fd: c_int) c_int;
extern fn lseek(fd: c_int, offset: isize, whence: c_int) isize;
extern fn malloc(size: usize) ?*anyopaque;
extern fn free(ptr: ?*anyopaque) void;
extern fn mmap(addr: ?*anyopaque, length: usize, prot: c_int, flags: c_int, fd: c_int, offset: isize) *anyopaque;
extern fn madvise(addr: ?*anyopaque, length: usize, advice: c_int) c_int;
extern fn usleep(usec: c_uint) c_int;
extern fn clock_gettime(clock_id: c_int, tp: *TimeSpec) c_int;
extern fn pthread_create(thread: *usize, attr: ?*anyopaque, start_routine: *const fn (?*anyopaque) callconv(.c) ?*anyopaque, arg: ?*anyopaque) c_int;
extern fn pthread_join(thread: usize, retval: ?*?*anyopaque) c_int;

const O_RDONLY: c_int = 0;
const O_WRONLY: c_int = 1;
const O_CREAT: c_int = 0x40;
const O_TRUNC: c_int = 0x200;
const SEEK_SET: c_int = 0;
const SEEK_END: c_int = 2;
const PROT_READ: c_int = 0x1;
const MAP_PRIVATE: c_int = 0x02;
const MADV_SEQUENTIAL: c_int = 2;
const MADV_WILLNEED: c_int = 3;
const CLOCK_MONOTONIC: c_int = 1;
const kEmptyCstr: [*:0]const u8 = "";

const kBosTokenId: u32 = 2;
const kUnkTokenId: u32 = 3;
const kMaxTokenCapacity: usize = 8192;
const kMaxTextBytes: usize = 65536;
const kMaxPath: usize = 4096;
const kPackedHeaderBytes: usize = 128;
const kDefaultBinBufferBytes: usize = 1 << 20;
const kMaxBatchJobs: usize = 2048;

const TokenEntry = extern struct {
    hash: u64,
    offset: u32,
    len: u32,
    id: u32,
    used: u8,
};

const MergeEntry = extern struct {
    key: u64,
    rank: u32,
    merged_id: u32,
    used: u8,
};

const Segment = extern struct {
    role: u8,
    byte_start: u32,
    byte_end: u32,
    token_start: u32,
    token_end: u32,
    loss_mask: u8,
};

const Context = struct {
    token_entries: [*]TokenEntry,
    token_cap: usize,
    token_storage: [*]u8,
    token_storage_len: usize,
    token_storage_cap: usize,
    merge_entries: [*]MergeEntry,
    merge_cap: usize,
    byte_fallback: [256]u32,
    audit_allocations: bool,
    audited_allocations: u64,
};

const BufferedWriter = struct {
    fd: c_int,
    buf: [*]u8,
    cap: usize,
    pos: usize,
    write_calls: u64,
    flush_count: u64,
    bytes_written: u64,
};

const TimeSpec = extern struct {
    tv_sec: isize,
    tv_nsec: isize,
};

const BpeMetrics = struct {
    records: u64,
    texts: u64,
    initial_symbols: u64,
    final_tokens: u64,
    merge_count: u64,
    pair_lookups: u64,
    successful_merge_lookups: u64,
    scan_passes: u64,
    compaction_moves: u64,
    max_initial_symbols: u64,
    max_final_tokens: u64,
    heap_pushes: u64,
    heap_pops: u64,
    heap_stale_pops: u64,
    heap_max_len: u64,
};

fn initBpeMetrics() BpeMetrics {
    return BpeMetrics{
        .records = 0,
        .texts = 0,
        .initial_symbols = 0,
        .final_tokens = 0,
        .merge_count = 0,
        .pair_lookups = 0,
        .successful_merge_lookups = 0,
        .scan_passes = 0,
        .compaction_moves = 0,
        .max_initial_symbols = 0,
        .max_final_tokens = 0,
        .heap_pushes = 0,
        .heap_pops = 0,
        .heap_stale_pops = 0,
        .heap_max_len = 0,
    };
}

const HeapEntry = struct {
    rank: u32,
    index: usize,
    left: u32,
    right: u32,
    merged_id: u32,
};

fn heapLess(a: HeapEntry, b: HeapEntry) bool {
    if (a.rank != b.rank) return a.rank < b.rank;
    return a.index < b.index;
}

fn heapPush(heap: []HeapEntry, len: *usize, item: HeapEntry, metrics: ?*BpeMetrics) bool {
    if (len.* >= heap.len) return false;
    var i = len.*;
    heap[i] = item;
    len.* += 1;
    if (metrics) |m| {
        m.heap_pushes += 1;
        if (len.* > m.heap_max_len) m.heap_max_len = len.*;
    }
    while (i > 0) {
        const parent = (i - 1) / 2;
        if (!heapLess(heap[i], heap[parent])) break;
        const tmp = heap[parent];
        heap[parent] = heap[i];
        heap[i] = tmp;
        i = parent;
    }
    return true;
}

fn heapPop(heap: []HeapEntry, len: *usize, metrics: ?*BpeMetrics) ?HeapEntry {
    if (len.* == 0) return null;
    if (metrics) |m| m.heap_pops += 1;
    const out = heap[0];
    len.* -= 1;
    if (len.* > 0) {
        heap[0] = heap[len.*];
        var i: usize = 0;
        while (true) {
            const left = i * 2 + 1;
            const right = left + 1;
            if (left >= len.*) break;
            var best = left;
            if (right < len.* and heapLess(heap[right], heap[left])) best = right;
            if (!heapLess(heap[best], heap[i])) break;
            const tmp = heap[i];
            heap[i] = heap[best];
            heap[best] = tmp;
            i = best;
        }
    }
    return out;
}

fn cstrLen(ptr: [*:0]const u8) usize {
    var i: usize = 0;
    while (ptr[i] != 0) : (i += 1) {}
    return i;
}

fn cstrEq(ptr: [*:0]const u8, lit: []const u8) bool {
    const n = cstrLen(ptr);
    if (n != lit.len) return false;
    var i: usize = 0;
    while (i < n) : (i += 1) if (ptr[i] != lit[i]) return false;
    return true;
}

fn copyCstr(dst: []u8, src: [*:0]const u8) bool {
    const n = cstrLen(src);
    if (n + 1 > dst.len) return false;
    var i: usize = 0;
    while (i < n) : (i += 1) dst[i] = src[i];
    dst[n] = 0;
    return true;
}

fn makePath(dst: []u8, base: [*:0]const u8, leaf: []const u8) bool {
    const base_len = cstrLen(base);
    const need_slash = base_len > 0 and base[base_len - 1] != '/';
    const total = base_len + (if (need_slash) @as(usize, 1) else @as(usize, 0)) + leaf.len;
    if (total + 1 > dst.len) return false;
    var i: usize = 0;
    while (i < base_len) : (i += 1) dst[i] = base[i];
    if (need_slash) {
        dst[i] = '/';
        i += 1;
    }
    var j: usize = 0;
    while (j < leaf.len) : (j += 1) dst[i + j] = leaf[j];
    dst[total] = 0;
    return true;
}

fn xmalloc(ctx: *Context, size: usize) ?[*]u8 {
    if (ctx.audit_allocations) ctx.audited_allocations += 1;
    const ptr = malloc(size);
    if (ptr == null) return null;
    return @as([*]u8, @ptrCast(ptr.?));
}

fn zeroTokenEntries(entries: [*]TokenEntry, cap: usize) void {
    var i: usize = 0;
    while (i < cap) : (i += 1) entries[i] = TokenEntry{ .hash = 0, .offset = 0, .len = 0, .id = 0, .used = 0 };
}

fn zeroMergeEntries(entries: [*]MergeEntry, cap: usize) void {
    var i: usize = 0;
    while (i < cap) : (i += 1) entries[i] = MergeEntry{ .key = 0, .rank = 0, .merged_id = 0, .used = 0 };
}

fn hashBytes(bytes: []const u8) u64 {
    var h: u64 = 1469598103934665603;
    var i: usize = 0;
    while (i < bytes.len) : (i += 1) {
        h ^= bytes[i];
        h *%= 1099511628211;
    }
    return h;
}

fn pairKey(left: u32, right: u32) u64 {
    return (@as(u64, left) << 32) | @as(u64, right);
}

fn mixU64(value: u64) u64 {
    var x = value;
    x ^= x >> 30;
    x *%= 0xbf58476d1ce4e5b9;
    x ^= x >> 27;
    x *%= 0x94d049bb133111eb;
    x ^= x >> 31;
    return x;
}

fn nextPow2(value: usize) usize {
    var out: usize = 1;
    while (out < value) out <<= 1;
    return out;
}

fn readFile(path: [*:0]const u8, len_out: *usize) ?[*]u8 {
    const fd = open(path, O_RDONLY, 0);
    if (fd < 0) return null;
    const end = lseek(fd, 0, SEEK_END);
    if (end < 0) {
        _ = close(fd);
        return null;
    }
    _ = lseek(fd, 0, SEEK_SET);
    const size: usize = @intCast(end);
    const raw = malloc(size + 1);
    if (raw == null) {
        _ = close(fd);
        return null;
    }
    const data = @as([*]u8, @ptrCast(raw.?));
    var read_total: usize = 0;
    while (read_total < size) {
        const got = read(fd, data + read_total, size - read_total);
        if (got <= 0) {
            _ = close(fd);
            free(raw);
            return null;
        }
        read_total += @intCast(got);
    }
    data[size] = 0;
    _ = close(fd);
    len_out.* = size;
    return data;
}

fn mapFileReadOnlyWithAdvice(path: [*:0]const u8, len_out: *usize, advice: c_int) ?[*]u8 {
    const fd = open(path, O_RDONLY, 0);
    if (fd < 0) return null;
    const end = lseek(fd, 0, SEEK_END);
    if (end < 0) {
        _ = close(fd);
        return null;
    }
    const size: usize = @intCast(end);
    const mapped = mmap(null, size, PROT_READ, MAP_PRIVATE, fd, 0);
    _ = close(fd);
    if (@intFromPtr(mapped) == 0xffffffffffffffff) return null;
    if (advice != 0) _ = madvise(mapped, size, advice);
    len_out.* = size;
    return @as([*]u8, @ptrCast(mapped));
}

fn mapFileReadOnly(path: [*:0]const u8, len_out: *usize) ?[*]u8 {
    return mapFileReadOnlyWithAdvice(path, len_out, 0);
}

fn sleepMillis(ms: u32) void {
    var remaining = ms;
    while (remaining > 0) {
        const chunk: u32 = if (remaining > 1000) 1000 else remaining;
        _ = usleep(@as(c_uint, @intCast(chunk * 1000)));
        remaining -= chunk;
    }
}

fn nowMonotonicNs() u64 {
    var ts = TimeSpec{ .tv_sec = 0, .tv_nsec = 0 };
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0;
    return @as(u64, @intCast(ts.tv_sec)) * 1000000000 + @as(u64, @intCast(ts.tv_nsec));
}

fn writeAll(fd: c_int, bytes: []const u8) bool {
    var written: usize = 0;
    while (written < bytes.len) {
        const n = write(fd, bytes.ptr + written, bytes.len - written);
        if (n <= 0) return false;
        written += @intCast(n);
    }
    return true;
}

fn initBufferedWriter(fd: c_int, cap: usize) ?BufferedWriter {
    const raw = malloc(cap);
    if (raw == null) return null;
    return BufferedWriter{
        .fd = fd,
        .buf = @as([*]u8, @ptrCast(raw.?)),
        .cap = cap,
        .pos = 0,
        .write_calls = 0,
        .flush_count = 0,
        .bytes_written = 0,
    };
}

fn flushBufferedWriter(writer: *BufferedWriter) bool {
    if (writer.pos == 0) return true;
    var written: usize = 0;
    while (written < writer.pos) {
        const n = write(writer.fd, writer.buf + written, writer.pos - written);
        if (n <= 0) return false;
        written += @intCast(n);
        writer.write_calls += 1;
        writer.bytes_written += @intCast(n);
    }
    writer.flush_count += 1;
    writer.pos = 0;
    return true;
}

fn bufferedWriteAll(writer: *BufferedWriter, bytes: []const u8) bool {
    if (bytes.len == 0) return true;
    if (bytes.len > writer.cap) {
        if (!flushBufferedWriter(writer)) return false;
        var written: usize = 0;
        while (written < bytes.len) {
            const n = write(writer.fd, bytes.ptr + written, bytes.len - written);
            if (n <= 0) return false;
            written += @intCast(n);
            writer.write_calls += 1;
            writer.bytes_written += @intCast(n);
        }
        writer.flush_count += 1;
        return true;
    }
    if (writer.pos + bytes.len > writer.cap) {
        if (!flushBufferedWriter(writer)) return false;
    }
    var i: usize = 0;
    while (i < bytes.len) : (i += 1) writer.buf[writer.pos + i] = bytes[i];
    writer.pos += bytes.len;
    return true;
}

fn bufferedWriteByte(writer: *BufferedWriter, byte: u8) bool {
    var one = [_]u8{byte};
    return bufferedWriteAll(writer, one[0..]);
}

fn bufferedWriteU16LE(writer: *BufferedWriter, value: u16) bool {
    var b = [_]u8{
        @intCast(value & 0xff),
        @intCast((value >> 8) & 0xff),
    };
    return bufferedWriteAll(writer, b[0..]);
}

fn bufferedWriteU32LE(writer: *BufferedWriter, value: u32) bool {
    var b: [4]u8 = undefined;
    b[0] = @intCast(value & 0xff);
    b[1] = @intCast((value >> 8) & 0xff);
    b[2] = @intCast((value >> 16) & 0xff);
    b[3] = @intCast((value >> 24) & 0xff);
    return bufferedWriteAll(writer, b[0..]);
}

fn bufferedWriteU64LE(writer: *BufferedWriter, value: u64) bool {
    var b: [8]u8 = undefined;
    var i: usize = 0;
    while (i < 8) : (i += 1) b[i] = @intCast((value >> @intCast(i * 8)) & 0xff);
    return bufferedWriteAll(writer, b[0..]);
}

fn writeByte(fd: c_int, byte: u8) bool {
    var one = [_]u8{byte};
    return writeAll(fd, one[0..]);
}

fn writeU16LE(fd: c_int, value: u16) bool {
    var b = [_]u8{
        @intCast(value & 0xff),
        @intCast((value >> 8) & 0xff),
    };
    return writeAll(fd, b[0..]);
}

fn writeU32LE(fd: c_int, value: u32) bool {
    var b: [4]u8 = undefined;
    b[0] = @intCast(value & 0xff);
    b[1] = @intCast((value >> 8) & 0xff);
    b[2] = @intCast((value >> 16) & 0xff);
    b[3] = @intCast((value >> 24) & 0xff);
    return writeAll(fd, b[0..]);
}

fn writeU64LE(fd: c_int, value: u64) bool {
    var b: [8]u8 = undefined;
    var i: usize = 0;
    while (i < 8) : (i += 1) b[i] = @intCast((value >> @intCast(i * 8)) & 0xff);
    return writeAll(fd, b[0..]);
}

fn readU16LEMem(bytes: []const u8, offset: usize) ?u16 {
    if (offset + 2 > bytes.len) return null;
    return @as(u16, bytes[offset]) | (@as(u16, bytes[offset + 1]) << 8);
}

fn readU32LEMem(bytes: []const u8, offset: usize) ?u32 {
    if (offset + 4 > bytes.len) return null;
    return @as(u32, bytes[offset]) |
        (@as(u32, bytes[offset + 1]) << 8) |
        (@as(u32, bytes[offset + 2]) << 16) |
        (@as(u32, bytes[offset + 3]) << 24);
}

fn readU64LEMem(bytes: []const u8, offset: usize) ?u64 {
    if (offset + 8 > bytes.len) return null;
    var out: u64 = 0;
    var i: usize = 0;
    while (i < 8) : (i += 1) out |= @as(u64, bytes[offset + i]) << @intCast(i * 8);
    return out;
}

fn writeDec(fd: c_int, value: u64) bool {
    var buf: [32]u8 = undefined;
    var n = value;
    var pos: usize = buf.len;
    if (n == 0) {
        pos -= 1;
        buf[pos] = '0';
    } else {
        while (n > 0) {
            pos -= 1;
            buf[pos] = @intCast('0' + (n % 10));
            n /= 10;
        }
    }
    return writeAll(fd, buf[pos..]);
}

fn hexValue(c: u8) ?u8 {
    if (c >= '0' and c <= '9') return c - '0';
    if (c >= 'a' and c <= 'f') return 10 + c - 'a';
    if (c >= 'A' and c <= 'F') return 10 + c - 'A';
    return null;
}

fn decodeHexTo(input: []const u8, output: []u8) ?usize {
    if ((input.len & 1) != 0) return null;
    const count = input.len / 2;
    if (count > output.len) return null;
    var i: usize = 0;
    while (i < count) : (i += 1) {
        const hi = hexValue(input[i * 2]) orelse return null;
        const lo = hexValue(input[i * 2 + 1]) orelse return null;
        output[i] = (hi << 4) | lo;
    }
    return count;
}

fn parseU32(bytes: []const u8) ?u32 {
    if (bytes.len == 0) return null;
    var out: u32 = 0;
    var i: usize = 0;
    while (i < bytes.len) : (i += 1) {
        const c = bytes[i];
        if (c < '0' or c > '9') return null;
        out = out * 10 + @as(u32, c - '0');
    }
    return out;
}

fn insertToken(ctx: *Context, token: []const u8, id: u32) bool {
    if (ctx.token_storage_len + token.len > ctx.token_storage_cap) return false;
    const offset = ctx.token_storage_len;
    var i: usize = 0;
    while (i < token.len) : (i += 1) ctx.token_storage[offset + i] = token[i];
    ctx.token_storage_len += token.len;
    const h = hashBytes(token);
    var index = @as(usize, @intCast(h)) & (ctx.token_cap - 1);
    while (true) {
        if (ctx.token_entries[index].used == 0) {
            ctx.token_entries[index] = TokenEntry{
                .hash = h,
                .offset = @intCast(offset),
                .len = @intCast(token.len),
                .id = id,
                .used = 1,
            };
            return true;
        }
        index = (index + 1) & (ctx.token_cap - 1);
    }
}

fn lookupToken(ctx: *const Context, token: []const u8) ?u32 {
    const h = hashBytes(token);
    var index = @as(usize, @intCast(h)) & (ctx.token_cap - 1);
    while (true) {
        const e = ctx.token_entries[index];
        if (e.used == 0) return null;
        if (e.hash == h and e.len == token.len) {
            const start: usize = @intCast(e.offset);
            var same = true;
            var i: usize = 0;
            while (i < token.len) : (i += 1) {
                if (ctx.token_storage[start + i] != token[i]) {
                    same = false;
                    break;
                }
            }
            if (same) return e.id;
        }
        index = (index + 1) & (ctx.token_cap - 1);
    }
}

fn insertMerge(ctx: *Context, left: u32, right: u32, rank: u32, merged_id: u32) void {
    const key = pairKey(left, right);
    var index = @as(usize, @intCast(mixU64(key))) & (ctx.merge_cap - 1);
    while (true) {
        if (ctx.merge_entries[index].used == 0) {
            ctx.merge_entries[index] = MergeEntry{ .key = key, .rank = rank, .merged_id = merged_id, .used = 1 };
            return;
        }
        index = (index + 1) & (ctx.merge_cap - 1);
    }
}

fn lookupMerge(ctx: *const Context, left: u32, right: u32) ?MergeEntry {
    const key = pairKey(left, right);
    var index = @as(usize, @intCast(mixU64(key))) & (ctx.merge_cap - 1);
    while (true) {
        const e = ctx.merge_entries[index];
        if (e.used == 0) return null;
        if (e.key == key) return e;
        index = (index + 1) & (ctx.merge_cap - 1);
    }
}

fn countLines(bytes: []const u8) usize {
    var count: usize = 0;
    var i: usize = 0;
    while (i < bytes.len) : (i += 1) {
        if (bytes[i] == '\n') count += 1;
    }
    return count + 1;
}

fn loadVocab(ctx: *Context, path: [*:0]const u8) bool {
    var len: usize = 0;
    const data = readFile(path, &len) orelse return false;
    const line_count = countLines(data[0..len]);
    ctx.token_cap = nextPow2(line_count * 2 + 16);
    ctx.token_storage_cap = len / 2 + 4096;
    const token_entries_raw = malloc(ctx.token_cap * @sizeOf(TokenEntry)) orelse return false;
    ctx.token_entries = @as([*]TokenEntry, @ptrCast(@alignCast(token_entries_raw)));
    ctx.token_storage = @as([*]u8, @ptrCast((malloc(ctx.token_storage_cap) orelse return false)));
    ctx.token_storage_len = 0;
    zeroTokenEntries(ctx.token_entries, ctx.token_cap);
    var line_start: usize = 0;
    var tmp: [8192]u8 = undefined;
    var i: usize = 0;
    while (i <= len) : (i += 1) {
        if (i == len or data[i] == '\n') {
            var line_end = i;
            if (line_end > line_start and data[line_end - 1] == '\r') line_end -= 1;
            if (line_end > line_start) {
                var tab: usize = line_start;
                while (tab < line_end and data[tab] != '\t') : (tab += 1) {}
                if (tab < line_end) {
                    const token_len = decodeHexTo(data[line_start..tab], tmp[0..]) orelse return false;
                    const id = parseU32(data[tab + 1 .. line_end]) orelse return false;
                    if (!insertToken(ctx, tmp[0..token_len], id)) return false;
                }
            }
            line_start = i + 1;
        }
    }
    var b: u32 = 0;
    var fallback: [6]u8 = undefined;
    while (b < 256) : (b += 1) {
        fallback[0] = '<';
        fallback[1] = '0';
        fallback[2] = 'x';
        const hi = (b >> 4) & 15;
        const lo = b & 15;
        fallback[3] = if (hi < 10) @intCast('0' + hi) else @intCast('A' + hi - 10);
        fallback[4] = if (lo < 10) @intCast('0' + lo) else @intCast('A' + lo - 10);
        fallback[5] = '>';
        ctx.byte_fallback[b] = lookupToken(ctx, fallback[0..]) orelse kUnkTokenId;
    }
    free(data);
    return true;
}

fn loadMerges(ctx: *Context, path: [*:0]const u8) bool {
    var len: usize = 0;
    const data = readFile(path, &len) orelse return false;
    const line_count = countLines(data[0..len]);
    ctx.merge_cap = nextPow2(line_count * 2 + 16);
    const merge_entries_raw = malloc(ctx.merge_cap * @sizeOf(MergeEntry)) orelse return false;
    ctx.merge_entries = @as([*]MergeEntry, @ptrCast(@alignCast(merge_entries_raw)));
    zeroMergeEntries(ctx.merge_entries, ctx.merge_cap);
    var line_start: usize = 0;
    var left_buf: [4096]u8 = undefined;
    var right_buf: [4096]u8 = undefined;
    var merged_buf: [8192]u8 = undefined;
    var i: usize = 0;
    while (i <= len) : (i += 1) {
        if (i == len or data[i] == '\n') {
            var line_end = i;
            if (line_end > line_start and data[line_end - 1] == '\r') line_end -= 1;
            if (line_end > line_start) {
                var t1 = line_start;
                while (t1 < line_end and data[t1] != '\t') : (t1 += 1) {}
                var t2 = t1 + 1;
                while (t2 < line_end and data[t2] != '\t') : (t2 += 1) {}
                if (t1 < line_end and t2 < line_end) {
                    const left_len = decodeHexTo(data[line_start..t1], left_buf[0..]) orelse return false;
                    const right_len = decodeHexTo(data[t1 + 1 .. t2], right_buf[0..]) orelse return false;
                    if (left_len + right_len <= merged_buf.len) {
                        var j: usize = 0;
                        while (j < left_len) : (j += 1) merged_buf[j] = left_buf[j];
                        j = 0;
                        while (j < right_len) : (j += 1) merged_buf[left_len + j] = right_buf[j];
                        const left_id = lookupToken(ctx, left_buf[0..left_len]);
                        const right_id = lookupToken(ctx, right_buf[0..right_len]);
                        const merged_id = lookupToken(ctx, merged_buf[0 .. left_len + right_len]);
                        const rank = parseU32(data[t2 + 1 .. line_end]) orelse return false;
                        if (left_id != null and right_id != null and merged_id != null) {
                            insertMerge(ctx, left_id.?, right_id.?, rank, merged_id.?);
                        }
                    }
                }
            }
            line_start = i + 1;
        }
    }
    free(data);
    return true;
}

fn loadPackedTable(ctx: *Context, path: [*:0]const u8, use_mmap: bool) bool {
    var len: usize = 0;
    const data = if (use_mmap) (mapFileReadOnly(path, &len) orelse return false) else (readFile(path, &len) orelse return false);
    if (len < kPackedHeaderBytes or !bytesEq(data[0..4], "GBT1")) return false;
    const version = readU32LEMem(data[0..len], 4) orelse return false;
    if (version != 1) return false;
    const total_size = readU64LEMem(data[0..len], 8) orelse return false;
    if (total_size != len) return false;
    ctx.token_cap = @intCast(readU64LEMem(data[0..len], 16) orelse return false);
    const token_storage_len: usize = @intCast(readU64LEMem(data[0..len], 32) orelse return false);
    ctx.merge_cap = @intCast(readU64LEMem(data[0..len], 40) orelse return false);
    const token_entries_off: usize = @intCast(readU64LEMem(data[0..len], 56) orelse return false);
    const token_storage_off: usize = @intCast(readU64LEMem(data[0..len], 64) orelse return false);
    const merge_entries_off: usize = @intCast(readU64LEMem(data[0..len], 72) orelse return false);
    const byte_fallback_off: usize = @intCast(readU64LEMem(data[0..len], 80) orelse return false);
    const token_entries_bytes = ctx.token_cap * @sizeOf(TokenEntry);
    const merge_entries_bytes = ctx.merge_cap * @sizeOf(MergeEntry);
    if (token_entries_off + token_entries_bytes > len) return false;
    if (token_storage_off + token_storage_len > len) return false;
    if (merge_entries_off + merge_entries_bytes > len) return false;
    if (byte_fallback_off + 1024 > len) return false;
    ctx.token_entries = @as([*]TokenEntry, @ptrCast(@alignCast(data + token_entries_off)));
    ctx.token_storage = data + token_storage_off;
    ctx.token_storage_len = token_storage_len;
    ctx.token_storage_cap = token_storage_len;
    ctx.merge_entries = @as([*]MergeEntry, @ptrCast(@alignCast(data + merge_entries_off)));
    var i: usize = 0;
    while (i < 256) : (i += 1) {
        ctx.byte_fallback[i] = readU32LEMem(data[0..len], byte_fallback_off + i * 4) orelse return false;
    }
    return true;
}

fn utf8Width(text: []const u8, index: usize) usize {
    const b = text[index];
    var width: usize = 1;
    if ((b & 0x80) == 0) width = 1 else if ((b & 0xe0) == 0xc0) width = 2 else if ((b & 0xf0) == 0xe0) width = 3 else if ((b & 0xf8) == 0xf0) width = 4;
    if (index + width > text.len) return text.len - index;
    return width;
}

fn encodeText(ctx: *const Context, text: []const u8, out: []u32, symbols: []u32, metrics: ?*BpeMetrics) ?usize {
    var symbol_count: usize = 0;
    var index: usize = 0;
    while (index < text.len) {
        if (symbol_count >= symbols.len) return null;
        if (text[index] == ' ') {
            const sp = [_]u8{ 0xe2, 0x96, 0x81 };
            symbols[symbol_count] = lookupToken(ctx, sp[0..]) orelse kUnkTokenId;
            symbol_count += 1;
            index += 1;
            continue;
        }
        const width = utf8Width(text, index);
        const piece = text[index .. index + width];
        const found = lookupToken(ctx, piece);
        if (found != null) {
            symbols[symbol_count] = found.?;
            symbol_count += 1;
        } else {
            var b: usize = 0;
            while (b < width) : (b += 1) {
                if (symbol_count >= symbols.len) return null;
                symbols[symbol_count] = ctx.byte_fallback[piece[b]];
                symbol_count += 1;
            }
        }
        index += width;
    }
    const initial_symbol_count = symbol_count;
    while (symbol_count > 1) {
        if (metrics) |m| m.scan_passes += 1;
        var best_rank: u32 = 0xffffffff;
        var best_index: usize = symbol_count;
        var best_merged: u32 = kUnkTokenId;
        var i: usize = 0;
        while (i + 1 < symbol_count) : (i += 1) {
            if (metrics) |m| m.pair_lookups += 1;
            const found = lookupMerge(ctx, symbols[i], symbols[i + 1]);
            if (found != null) {
                if (metrics) |m| m.successful_merge_lookups += 1;
            }
            if (found != null and found.?.rank < best_rank) {
                best_rank = found.?.rank;
                best_index = i;
                best_merged = found.?.merged_id;
            }
        }
        if (best_index == symbol_count) break;
        symbols[best_index] = best_merged;
        var j = best_index + 1;
        while (j + 1 < symbol_count) : (j += 1) {
            symbols[j] = symbols[j + 1];
            if (metrics) |m| m.compaction_moves += 1;
        }
        symbol_count -= 1;
        if (metrics) |m| m.merge_count += 1;
    }
    if (symbol_count > out.len) return null;
    var k: usize = 0;
    while (k < symbol_count) : (k += 1) out[k] = symbols[k];
    if (metrics) |m| {
        m.texts += 1;
        m.initial_symbols += initial_symbol_count;
        m.final_tokens += symbol_count;
        if (initial_symbol_count > m.max_initial_symbols) m.max_initial_symbols = initial_symbol_count;
        if (symbol_count > m.max_final_tokens) m.max_final_tokens = symbol_count;
    }
    return symbol_count;
}

fn seedSymbols(ctx: *const Context, text: []const u8, symbols: []u32) ?usize {
    var symbol_count: usize = 0;
    var index: usize = 0;
    while (index < text.len) {
        if (symbol_count >= symbols.len) return null;
        if (text[index] == ' ') {
            const sp = [_]u8{ 0xe2, 0x96, 0x81 };
            symbols[symbol_count] = lookupToken(ctx, sp[0..]) orelse kUnkTokenId;
            symbol_count += 1;
            index += 1;
            continue;
        }
        const width = utf8Width(text, index);
        const piece = text[index .. index + width];
        const found = lookupToken(ctx, piece);
        if (found != null) {
            symbols[symbol_count] = found.?;
            symbol_count += 1;
        } else {
            var b: usize = 0;
            while (b < width) : (b += 1) {
                if (symbol_count >= symbols.len) return null;
                symbols[symbol_count] = ctx.byte_fallback[piece[b]];
                symbol_count += 1;
            }
        }
        index += width;
    }
    return symbol_count;
}

fn heapPushPair(ctx: *const Context, symbols: []u32, next: []usize, active: []u8, index: usize, heap: []HeapEntry, heap_len: *usize, metrics: ?*BpeMetrics) bool {
    if (active[index] == 0) return true;
    const right_index = next[index];
    if (right_index >= symbols.len or active[right_index] == 0) return true;
    if (metrics) |m| m.pair_lookups += 1;
    const found = lookupMerge(ctx, symbols[index], symbols[right_index]);
    if (found == null) return true;
    if (metrics) |m| m.successful_merge_lookups += 1;
    return heapPush(heap, heap_len, HeapEntry{ .rank = found.?.rank, .index = index, .left = symbols[index], .right = symbols[right_index], .merged_id = found.?.merged_id }, metrics);
}

fn encodeTextHeap(ctx: *const Context, text: []const u8, out: []u32, symbols: []u32, prev: []usize, next: []usize, active: []u8, heap: []HeapEntry, metrics: ?*BpeMetrics) ?usize {
    var symbol_count = seedSymbols(ctx, text, symbols) orelse return null;
    const initial_symbol_count = symbol_count;
    var i: usize = 0;
    while (i < symbol_count) : (i += 1) {
        prev[i] = if (i == 0) kMaxTokenCapacity else i - 1;
        next[i] = if (i + 1 < symbol_count) i + 1 else kMaxTokenCapacity;
        active[i] = 1;
    }
    var heap_len: usize = 0;
    i = 0;
    while (i + 1 < symbol_count) : (i += 1) {
        if (!heapPushPair(ctx, symbols, next, active, i, heap, &heap_len, metrics)) return null;
    }
    while (symbol_count > 1) {
        const item = heapPop(heap, &heap_len, metrics) orelse break;
        if (item.index >= symbols.len or active[item.index] == 0) {
            if (metrics) |m| m.heap_stale_pops += 1;
            continue;
        }
        const right_index = next[item.index];
        if (right_index >= symbols.len or active[right_index] == 0 or symbols[item.index] != item.left or symbols[right_index] != item.right) {
            if (metrics) |m| m.heap_stale_pops += 1;
            continue;
        }
        symbols[item.index] = item.merged_id;
        active[right_index] = 0;
        const next_right = next[right_index];
        next[item.index] = next_right;
        if (next_right < symbols.len) prev[next_right] = item.index;
        symbol_count -= 1;
        if (metrics) |m| m.merge_count += 1;
        const left_index = prev[item.index];
        if (left_index < symbols.len) {
            if (!heapPushPair(ctx, symbols, next, active, left_index, heap, &heap_len, metrics)) return null;
        }
        if (!heapPushPair(ctx, symbols, next, active, item.index, heap, &heap_len, metrics)) return null;
    }
    var out_count: usize = 0;
    i = 0;
    while (i < initial_symbol_count) : (i += 1) {
        if (active[i] != 0) {
            if (out_count >= out.len) return null;
            out[out_count] = symbols[i];
            out_count += 1;
        }
    }
    if (metrics) |m| {
        m.texts += 1;
        m.initial_symbols += initial_symbol_count;
        m.final_tokens += out_count;
        if (initial_symbol_count > m.max_initial_symbols) m.max_initial_symbols = initial_symbol_count;
        if (out_count > m.max_final_tokens) m.max_final_tokens = out_count;
    }
    return out_count;
}

fn extractString(line: []const u8, key: []const u8, out: []u8) ?usize {
    var i: usize = 0;
    while (i + key.len + 2 < line.len) : (i += 1) {
        if (line[i] != '"') continue;
        var same = true;
        var k: usize = 0;
        while (k < key.len) : (k += 1) {
            if (line[i + 1 + k] != key[k]) same = false;
        }
        if (!same or line[i + 1 + key.len] != '"') continue;
        var p = i + key.len + 2;
        while (p < line.len and (line[p] == ' ' or line[p] == '\t')) : (p += 1) {}
        if (p >= line.len or line[p] != ':') return null;
        p += 1;
        while (p < line.len and (line[p] == ' ' or line[p] == '\t')) : (p += 1) {}
        if (p >= line.len or line[p] != '"') return null;
        p += 1;
        var n: usize = 0;
        while (p < line.len) : (p += 1) {
            const c = line[p];
            if (c == '"') return n;
            if (n >= out.len) return null;
            if (c == '\\') {
                p += 1;
                if (p >= line.len) return null;
                const e = line[p];
                out[n] = if (e == 'n') '\n' else if (e == 'r') '\r' else if (e == 't') '\t' else e;
            } else {
                out[n] = c;
            }
            n += 1;
        }
        return null;
    }
    return null;
}

fn sourceKindEnum(kind: []const u8) u8 {
    if (bytesEq(kind, "dictionary")) return 1;
    if (bytesEq(kind, "megascience")) return 2;
    if (bytesEq(kind, "synthetic_stress")) return 3;
    if (bytesEq(kind, "user_supplied")) return 4;
    return 0;
}

fn sourceKindName(kind: u8) []const u8 {
    if (kind == 1) return "dictionary";
    if (kind == 2) return "megascience";
    if (kind == 3) return "synthetic_stress";
    if (kind == 4) return "user_supplied";
    return "unknown";
}

fn bytesEq(a: []const u8, b: []const u8) bool {
    if (a.len != b.len) return false;
    var i: usize = 0;
    while (i < a.len) : (i += 1) if (a[i] != b[i]) return false;
    return true;
}

fn writeJsonEscaped(fd: c_int, bytes: []const u8) bool {
    if (!writeByte(fd, '"')) return false;
    var i: usize = 0;
    while (i < bytes.len) : (i += 1) {
        const c = bytes[i];
        if (c == '"' or c == '\\') {
            if (!writeByte(fd, '\\') or !writeByte(fd, c)) return false;
        } else if (c == '\n') {
            if (!writeAll(fd, "\\n")) return false;
        } else if (c == '\r') {
            if (!writeAll(fd, "\\r")) return false;
        } else if (c == '\t') {
            if (!writeAll(fd, "\\t")) return false;
        } else {
            if (!writeByte(fd, c)) return false;
        }
    }
    return writeByte(fd, '"');
}

fn writeEvidenceRecord(fd: c_int, record_id: []const u8, kind: []const u8, token_ids: []const u32, q_span: Segment, a_span: Segment, vocab_sha: [*:0]const u8, merges_sha: [*:0]const u8) bool {
    if (!writeAll(fd, "{\"schema_version\":\"polar_phase1_qa_ingest_record_v1\",\"record_id\":")) return false;
    if (!writeJsonEscaped(fd, record_id)) return false;
    if (!writeAll(fd, ",\"source_kind\":")) return false;
    if (!writeJsonEscaped(fd, kind)) return false;
    if (!writeAll(fd, ",\"source_hash\":\"fnv1a64:")) return false;
    if (!writeDec(fd, hashBytes(record_id))) return false;
    if (!writeAll(fd, "\",\"tokenizer_ref\":{\"model_id\":\"google/gemma-4-E4B\",\"revision\":\"7aa32e6889efd6300124851b164f8b364314c3d8\",\"vocab_sha256\":\"")) return false;
    if (!writeAll(fd, vocab_sha[0..cstrLen(vocab_sha)])) return false;
    if (!writeAll(fd, "\",\"merges_sha256\":\"")) return false;
    if (!writeAll(fd, merges_sha[0..cstrLen(merges_sha)])) return false;
    if (!writeAll(fd, "\"},\"token_ids\":[")) return false;
    var i: usize = 0;
    while (i < token_ids.len) : (i += 1) {
        if (i != 0 and !writeByte(fd, ',')) return false;
        if (!writeDec(fd, token_ids[i])) return false;
    }
    if (!writeAll(fd, "],\"segments\":[")) return false;
    if (!writeAll(fd, "{\"role\":\"question\",\"byte_start\":0,\"byte_end\":")) return false;
    if (!writeDec(fd, q_span.byte_end)) return false;
    if (!writeAll(fd, ",\"token_start\":")) return false;
    if (!writeDec(fd, q_span.token_start)) return false;
    if (!writeAll(fd, ",\"token_end\":")) return false;
    if (!writeDec(fd, q_span.token_end)) return false;
    if (!writeAll(fd, ",\"loss_mask\":\"none\"},{\"role\":\"answer\",\"byte_start\":0,\"byte_end\":")) return false;
    if (!writeDec(fd, a_span.byte_end)) return false;
    if (!writeAll(fd, ",\"token_start\":")) return false;
    if (!writeDec(fd, a_span.token_start)) return false;
    if (!writeAll(fd, ",\"token_end\":")) return false;
    if (!writeDec(fd, a_span.token_end)) return false;
    if (!writeAll(fd, ",\"loss_mask\":\"target\"}],\"loss_mask\":[")) return false;
    i = 0;
    while (i < token_ids.len) : (i += 1) {
        if (i != 0 and !writeByte(fd, ',')) return false;
        const active = if (i >= a_span.token_start and i < a_span.token_end) "1" else "0";
        if (!writeAll(fd, active)) return false;
    }
    return writeAll(fd, "],\"position_policy\":\"monotonic_record_local\",\"continuation_policy\":\"record_local\",\"nonclaims\":[\"no_jl_packetization\",\"no_npu_forward_read\",\"no_gpu_optimizer\",\"no_learning_claim\",\"no_megakernel_claim\"]}\n");
}

fn writeEvidenceIfEnabled(fd: c_int, record_id: []const u8, kind: []const u8, token_ids: []const u32, q_span: Segment, a_span: Segment, vocab_sha: [*:0]const u8, merges_sha: [*:0]const u8) bool {
    if (fd < 0) return true;
    return writeEvidenceRecord(fd, record_id, kind, token_ids, q_span, a_span, vocab_sha, merges_sha);
}

fn writeBinaryRecord(writer: *BufferedWriter, record_id: []const u8, kind: []const u8, token_ids: []const u32, q_span: Segment, a_span: Segment) bool {
    if (!bufferedWriteU64LE(writer, hashBytes(record_id))) return false;
    if (!bufferedWriteByte(writer, sourceKindEnum(kind))) return false;
    if (!bufferedWriteU32LE(writer, @intCast(token_ids.len))) return false;
    if (!bufferedWriteU16LE(writer, 2)) return false;
    var i: usize = 0;
    while (i < token_ids.len) : (i += 1) if (!bufferedWriteU32LE(writer, token_ids[i])) return false;
    const spans = [_]Segment{ q_span, a_span };
    i = 0;
    while (i < spans.len) : (i += 1) {
        if (!bufferedWriteByte(writer, spans[i].role)) return false;
        if (!bufferedWriteU32LE(writer, spans[i].token_start)) return false;
        if (!bufferedWriteU32LE(writer, spans[i].token_end)) return false;
        if (!bufferedWriteU32LE(writer, spans[i].byte_start)) return false;
        if (!bufferedWriteU32LE(writer, spans[i].byte_end)) return false;
        if (!bufferedWriteByte(writer, spans[i].loss_mask)) return false;
    }
    return true;
}

fn writeHeader(writer: *BufferedWriter, record_count: u64, vocab_sha: [*:0]const u8, merges_sha: [*:0]const u8) bool {
    if (!bufferedWriteAll(writer, "PQA1")) return false;
    if (!bufferedWriteU16LE(writer, 1)) return false;
    if (!bufferedWriteU16LE(writer, 1)) return false;
    if (!bufferedWriteU64LE(writer, record_count)) return false;
    var i: usize = 0;
    while (i < 64) : (i += 1) {
        const c = if (i < cstrLen(vocab_sha)) vocab_sha[i] else '0';
        if (!bufferedWriteByte(writer, c)) return false;
    }
    i = 0;
    while (i < 64) : (i += 1) {
        const c = if (i < cstrLen(merges_sha)) merges_sha[i] else '0';
        if (!bufferedWriteByte(writer, c)) return false;
    }
    return true;
}

fn countValidQa(input: []const u8) u64 {
    var records: u64 = 0;
    var line_start: usize = 0;
    var rid: [1024]u8 = undefined;
    var kind: [64]u8 = undefined;
    var q: [kMaxTextBytes]u8 = undefined;
    var a: [kMaxTextBytes]u8 = undefined;
    var i: usize = 0;
    while (i <= input.len) : (i += 1) {
        if (i == input.len or input[i] == '\n') {
            const line = input[line_start..i];
            const rlen = extractString(line, "record_id", rid[0..]);
            const klen = extractString(line, "source_kind", kind[0..]);
            const qlen = extractString(line, "question", q[0..]);
            const alen = extractString(line, "answer", a[0..]);
            if (rlen != null and klen != null and qlen != null and alen != null and qlen.? > 0 and alen.? > 0) records += 1;
            line_start = i + 1;
        }
    }
    return records;
}

fn countValidBinaryQa(input: []const u8) ?u64 {
    if (input.len < 12 or !bytesEq(input[0..4], "QAI1")) return null;
    const records = readU64LEMem(input, 4) orelse return null;
    var offset: usize = 12;
    var seen: u64 = 0;
    while (seen < records) : (seen += 1) {
        if (offset + 11 > input.len) return null;
        offset += 1;
        const rid_len = readU16LEMem(input, offset) orelse return null;
        offset += 2;
        const q_len = readU32LEMem(input, offset) orelse return null;
        offset += 4;
        const a_len = readU32LEMem(input, offset) orelse return null;
        offset += 4;
        const total = @as(usize, rid_len) + @as(usize, q_len) + @as(usize, a_len);
        if (rid_len == 0 or q_len == 0 or a_len == 0 or offset + total > input.len) return null;
        offset += total;
    }
    if (offset != input.len) return null;
    return records;
}

fn encodeOneText(ctx: *const Context, text: []const u8, out: []u32, symbols: []u32, prev: []usize, next: []usize, active: []u8, heap: []HeapEntry, metrics: ?*BpeMetrics, use_heap_bpe: bool) ?usize {
    if (use_heap_bpe) return encodeTextHeap(ctx, text, out, symbols, prev, next, active, heap, metrics);
    return encodeText(ctx, text, out, symbols, metrics);
}

fn encodeAndWriteRecord(ctx: *const Context, json_fd: c_int, bin_writer: *BufferedWriter, record_id: []const u8, source_kind: []const u8, question: []const u8, answer: []const u8, q_tokens: []u32, a_tokens: []u32, symbols: []u32, prev: []usize, next: []usize, active: []u8, heap: []HeapEntry, token_ids: []u32, vocab_sha: [*:0]const u8, merges_sha: [*:0]const u8, bpe_metrics: ?*BpeMetrics, use_heap_bpe: bool) ?usize {
    const q_count = encodeOneText(ctx, question, q_tokens, symbols, prev, next, active, heap, bpe_metrics, use_heap_bpe) orelse return null;
    const a_count = encodeOneText(ctx, answer, a_tokens, symbols, prev, next, active, heap, bpe_metrics, use_heap_bpe) orelse return null;
    var count: usize = 0;
    token_ids[count] = kBosTokenId;
    count += 1;
    var j: usize = 0;
    while (j < q_count) : (j += 1) {
        token_ids[count] = q_tokens[j];
        count += 1;
    }
    const q_span = Segment{ .role = 1, .byte_start = 0, .byte_end = @intCast(question.len), .token_start = 1, .token_end = @intCast(1 + q_count), .loss_mask = 0 };
    j = 0;
    while (j < a_count) : (j += 1) {
        token_ids[count] = a_tokens[j];
        count += 1;
    }
    const a_span = Segment{ .role = 2, .byte_start = 0, .byte_end = @intCast(answer.len), .token_start = @intCast(1 + q_count), .token_end = @intCast(count), .loss_mask = 1 };
    if (!writeEvidenceIfEnabled(json_fd, record_id, source_kind, token_ids[0..count], q_span, a_span, vocab_sha, merges_sha)) return null;
    if (!writeBinaryRecord(bin_writer, record_id, source_kind, token_ids[0..count], q_span, a_span)) return null;
    if (bpe_metrics) |m| m.records += 1;
    return count;
}

fn writeBpeMetrics(path: [*:0]const u8, metrics: *const BpeMetrics, use_heap_bpe: bool) bool {
    if (cstrLen(path) == 0) return true;
    const fd = open(path, O_CREAT | O_TRUNC | O_WRONLY, 0o600);
    if (fd < 0) return false;
    var ok = true;
    ok = ok and writeAll(fd, "{\"schema_version\":\"polar_phase1_bpe_metrics_v1\",\"algorithm\":\"");
    ok = ok and writeAll(fd, if (use_heap_bpe) "heap" else "repeated_scan");
    ok = ok and writeAll(fd, "\",\"records\":");
    ok = ok and writeDec(fd, metrics.records);
    ok = ok and writeAll(fd, ",\"texts\":");
    ok = ok and writeDec(fd, metrics.texts);
    ok = ok and writeAll(fd, ",\"initial_symbols\":");
    ok = ok and writeDec(fd, metrics.initial_symbols);
    ok = ok and writeAll(fd, ",\"final_tokens\":");
    ok = ok and writeDec(fd, metrics.final_tokens);
    ok = ok and writeAll(fd, ",\"merge_count\":");
    ok = ok and writeDec(fd, metrics.merge_count);
    ok = ok and writeAll(fd, ",\"pair_lookups\":");
    ok = ok and writeDec(fd, metrics.pair_lookups);
    ok = ok and writeAll(fd, ",\"successful_merge_lookups\":");
    ok = ok and writeDec(fd, metrics.successful_merge_lookups);
    ok = ok and writeAll(fd, ",\"scan_passes\":");
    ok = ok and writeDec(fd, metrics.scan_passes);
    ok = ok and writeAll(fd, ",\"compaction_moves\":");
    ok = ok and writeDec(fd, metrics.compaction_moves);
    ok = ok and writeAll(fd, ",\"max_initial_symbols\":");
    ok = ok and writeDec(fd, metrics.max_initial_symbols);
    ok = ok and writeAll(fd, ",\"max_final_tokens\":");
    ok = ok and writeDec(fd, metrics.max_final_tokens);
    ok = ok and writeAll(fd, ",\"heap_pushes\":");
    ok = ok and writeDec(fd, metrics.heap_pushes);
    ok = ok and writeAll(fd, ",\"heap_pops\":");
    ok = ok and writeDec(fd, metrics.heap_pops);
    ok = ok and writeAll(fd, ",\"heap_stale_pops\":");
    ok = ok and writeDec(fd, metrics.heap_stale_pops);
    ok = ok and writeAll(fd, ",\"heap_max_len\":");
    ok = ok and writeDec(fd, metrics.heap_max_len);
    ok = ok and writeAll(fd, "}\n");
    _ = close(fd);
    return ok;
}

fn writeWriterMetrics(path: [*:0]const u8, writer: *const BufferedWriter, buffer_bytes: usize) bool {
    if (cstrLen(path) == 0) return true;
    const fd = open(path, O_CREAT | O_TRUNC | O_WRONLY, 0o600);
    if (fd < 0) return false;
    var ok = true;
    ok = ok and writeAll(fd, "{\"schema_version\":\"polar_phase1_writer_metrics_v1\",\"writer\":\"buffered_pqa1\",\"buffer_bytes\":");
    ok = ok and writeDec(fd, buffer_bytes);
    ok = ok and writeAll(fd, ",\"write_calls\":");
    ok = ok and writeDec(fd, writer.write_calls);
    ok = ok and writeAll(fd, ",\"flush_count\":");
    ok = ok and writeDec(fd, writer.flush_count);
    ok = ok and writeAll(fd, ",\"bytes_written\":");
    ok = ok and writeDec(fd, writer.bytes_written);
    ok = ok and writeAll(fd, "}\n");
    _ = close(fd);
    return ok;
}

fn writeBatchMetrics(path: [*:0]const u8, args: []const BatchThreadArg, job_count: usize) bool {
    if (cstrLen(path) == 0) return true;
    const fd = open(path, O_CREAT | O_TRUNC | O_WRONLY, 0o600);
    if (fd < 0) return false;
    var min_start: u64 = 0xffffffffffffffff;
    var max_end: u64 = 0;
    var total_jobs_done: u64 = 0;
    var i: usize = 0;
    while (i < args.len) : (i += 1) {
        if (args[i].start_ns != 0 and args[i].start_ns < min_start) min_start = args[i].start_ns;
        if (args[i].end_ns > max_end) max_end = args[i].end_ns;
        total_jobs_done += args[i].jobs_done;
    }
    if (min_start == 0xffffffffffffffff) min_start = 0;
    var ok = true;
    ok = ok and writeAll(fd, "{\"schema_version\":\"polar_phase1_batch_metrics_v1\",\"scheduler\":\"atomic_pull_queue\",\"job_count\":");
    ok = ok and writeDec(fd, @intCast(job_count));
    ok = ok and writeAll(fd, ",\"worker_count\":");
    ok = ok and writeDec(fd, @intCast(args.len));
    ok = ok and writeAll(fd, ",\"total_jobs_done\":");
    ok = ok and writeDec(fd, total_jobs_done);
    ok = ok and writeAll(fd, ",\"min_start_ns\":");
    ok = ok and writeDec(fd, min_start);
    ok = ok and writeAll(fd, ",\"max_end_ns\":");
    ok = ok and writeDec(fd, max_end);
    ok = ok and writeAll(fd, ",\"elapsed_ns\":");
    ok = ok and writeDec(fd, if (max_end >= min_start) max_end - min_start else 0);
    ok = ok and writeAll(fd, ",\"workers\":[");
    i = 0;
    while (i < args.len) : (i += 1) {
        if (i != 0) ok = ok and writeAll(fd, ",");
        const worker_elapsed = if (args[i].end_ns >= args[i].start_ns) args[i].end_ns - args[i].start_ns else 0;
        const post_drain_idle = if (max_end >= args[i].end_ns) max_end - args[i].end_ns else 0;
        ok = ok and writeAll(fd, "{\"worker_index\":");
        ok = ok and writeDec(fd, @intCast(i));
        ok = ok and writeAll(fd, ",\"jobs_done\":");
        ok = ok and writeDec(fd, args[i].jobs_done);
        ok = ok and writeAll(fd, ",\"start_ns\":");
        ok = ok and writeDec(fd, args[i].start_ns);
        ok = ok and writeAll(fd, ",\"end_ns\":");
        ok = ok and writeDec(fd, args[i].end_ns);
        ok = ok and writeAll(fd, ",\"elapsed_ns\":");
        ok = ok and writeDec(fd, worker_elapsed);
        ok = ok and writeAll(fd, ",\"post_drain_idle_ns\":");
        ok = ok and writeDec(fd, post_drain_idle);
        ok = ok and writeAll(fd, "}");
    }
    ok = ok and writeAll(fd, "]}\n");
    _ = close(fd);
    return ok;
}

fn processOneBinaryInput(ctx: *Context, input_path: [*:0]const u8, out_bin: [*:0]const u8, vocab_sha: [*:0]const u8, merges_sha: [*:0]const u8, writer_metrics_path: [*:0]const u8, bpe_metrics_path: [*:0]const u8, use_heap_bpe: bool) c_int {
    var input_len: usize = 0;
    const input = mapFileReadOnlyWithAdvice(input_path, &input_len, MADV_SEQUENTIAL) orelse return 69;
    const valid_count = countValidBinaryQa(input[0..input_len]) orelse return 74;
    const bin_fd = open(out_bin, O_CREAT | O_TRUNC | O_WRONLY, 0o600);
    if (bin_fd < 0) return 71;
    var bin_writer = initBufferedWriter(bin_fd, kDefaultBinBufferBytes) orelse return 73;
    if (!writeHeader(&bin_writer, valid_count, vocab_sha, merges_sha)) return 72;

    var q_tokens: [kMaxTokenCapacity]u32 = undefined;
    var a_tokens: [kMaxTokenCapacity]u32 = undefined;
    var symbols: [kMaxTokenCapacity]u32 = undefined;
    var prev: [kMaxTokenCapacity]usize = undefined;
    var next: [kMaxTokenCapacity]usize = undefined;
    var active: [kMaxTokenCapacity]u8 = undefined;
    var heap: [kMaxTokenCapacity * 3]HeapEntry = undefined;
    var token_ids: [kMaxTokenCapacity * 2]u32 = undefined;
    var processed: u64 = 0;
    var total_tokens: u64 = 0;
    var bpe_metrics = initBpeMetrics();
    const bpe_metrics_ptr: ?*BpeMetrics = if (cstrLen(bpe_metrics_path) == 0) null else &bpe_metrics;
    ctx.audit_allocations = true;
    ctx.audited_allocations = 0;
    var offset: usize = 12;
    var seen: u64 = 0;
    while (seen < valid_count) : (seen += 1) {
        const kind_enum = input[offset];
        offset += 1;
        const rid_len = readU16LEMem(input[0..input_len], offset) orelse return 75;
        offset += 2;
        const q_len = readU32LEMem(input[0..input_len], offset) orelse return 76;
        offset += 4;
        const a_len = readU32LEMem(input[0..input_len], offset) orelse return 77;
        offset += 4;
        const rid_start = offset;
        const q_start = rid_start + @as(usize, rid_len);
        const a_start = q_start + @as(usize, q_len);
        const end = a_start + @as(usize, a_len);
        if (end > input_len) return 78;
        const kind_name = sourceKindName(kind_enum);
        const written = encodeAndWriteRecord(ctx, -1, &bin_writer, input[rid_start..q_start], kind_name, input[q_start..a_start], input[a_start..end], q_tokens[0..], a_tokens[0..], symbols[0..], prev[0..], next[0..], active[0..], heap[0..], token_ids[0..], vocab_sha, merges_sha, bpe_metrics_ptr, use_heap_bpe) orelse return 80;
        processed += 1;
        total_tokens += written;
        offset = end;
    }
    ctx.audit_allocations = false;
    if (!flushBufferedWriter(&bin_writer)) return 93;
    _ = close(bin_fd);
    if (!writeWriterMetrics(writer_metrics_path, &bin_writer, kDefaultBinBufferBytes)) return 94;
    if (bpe_metrics_ptr != null and !writeBpeMetrics(bpe_metrics_path, &bpe_metrics, use_heap_bpe)) return 102;
    if (processed != valid_count) return 90;
    if (ctx.audited_allocations != 0) return 91;
    if (total_tokens == 0xffffffffffffffff) return 92;
    return 0;
}

const BatchJob = struct {
    ctx: *const Context,
    input_path: [*:0]const u8,
    out_bin: [*:0]const u8,
    writer_metrics_path: [*:0]const u8,
    bpe_metrics_path: [*:0]const u8,
    vocab_sha: [*:0]const u8,
    merges_sha: [*:0]const u8,
    use_heap_bpe: bool,
    hold_worker_start_ms: u32,
    result: c_int,
};

const BatchThreadArg = struct {
    jobs: [*]BatchJob,
    job_count: usize,
    next_index: *usize,
    ctx: *const Context,
    use_heap_bpe: bool,
    hold_worker_start_ms: u32,
    jobs_done: u64,
    start_ns: u64,
    end_ns: u64,
    result: c_int,
};

fn dupCstr(bytes: []const u8) ?[*:0]u8 {
    const raw = malloc(bytes.len + 1);
    if (raw == null) return null;
    const out = @as([*]u8, @ptrCast(raw.?));
    var i: usize = 0;
    while (i < bytes.len) : (i += 1) out[i] = bytes[i];
    out[bytes.len] = 0;
    return @as([*:0]u8, @ptrCast(out));
}

fn batchWorker(arg: ?*anyopaque) callconv(.c) ?*anyopaque {
    const job: *BatchJob = @ptrCast(@alignCast(arg.?));
    if (job.hold_worker_start_ms != 0) sleepMillis(job.hold_worker_start_ms);
    var local_ctx = job.ctx.*;
    job.result = processOneBinaryInput(&local_ctx, job.input_path, job.out_bin, job.vocab_sha, job.merges_sha, job.writer_metrics_path, job.bpe_metrics_path, job.use_heap_bpe);
    return null;
}

fn batchQueueWorker(arg: ?*anyopaque) callconv(.c) ?*anyopaque {
    const worker: *BatchThreadArg = @ptrCast(@alignCast(arg.?));
    if (worker.hold_worker_start_ms != 0) sleepMillis(worker.hold_worker_start_ms);
    worker.start_ns = nowMonotonicNs();
    while (true) {
        const idx = @atomicRmw(usize, worker.next_index, .Add, 1, .seq_cst);
        if (idx >= worker.job_count) break;
        var local_ctx = worker.ctx.*;
        const rc = processOneBinaryInput(&local_ctx, worker.jobs[idx].input_path, worker.jobs[idx].out_bin, worker.jobs[idx].vocab_sha, worker.jobs[idx].merges_sha, worker.jobs[idx].writer_metrics_path, worker.jobs[idx].bpe_metrics_path, worker.use_heap_bpe);
        worker.jobs[idx].result = rc;
        worker.jobs_done += 1;
        if (rc != 0) worker.result = rc;
    }
    worker.end_ns = nowMonotonicNs();
    return null;
}

fn parseBatchList(path: [*:0]const u8, ctx: *const Context, vocab_sha: [*:0]const u8, merges_sha: [*:0]const u8, jobs: []BatchJob, count_out: *usize, use_heap_bpe: bool, hold_worker_start_ms: u32) c_int {
    var len: usize = 0;
    const data = readFile(path, &len) orelse return 95;
    var line_start: usize = 0;
    var count: usize = 0;
    var i: usize = 0;
    while (i <= len) : (i += 1) {
        if (i == len or data[i] == '\n') {
            var line_end = i;
            if (line_end > line_start and data[line_end - 1] == '\r') line_end -= 1;
            if (line_end > line_start) {
                if (count >= jobs.len) return 96;
                var t1 = line_start;
                while (t1 < line_end and data[t1] != '\t') : (t1 += 1) {}
                var t2 = t1 + 1;
                while (t2 < line_end and data[t2] != '\t') : (t2 += 1) {}
                if (t1 >= line_end or t2 >= line_end) return 97;
                var t3 = t2 + 1;
                while (t3 < line_end and data[t3] != '\t') : (t3 += 1) {}
                const input_path = dupCstr(data[line_start..t1]) orelse return 98;
                const out_bin = dupCstr(data[t1 + 1 .. t2]) orelse return 98;
                const writer_metrics_path = dupCstr(data[t2 + 1 .. if (t3 < line_end) t3 else line_end]) orelse return 98;
                const bpe_metrics_path = if (t3 < line_end) (dupCstr(data[t3 + 1 .. line_end]) orelse return 98) else kEmptyCstr;
                jobs[count] = BatchJob{
                    .ctx = ctx,
                    .input_path = input_path,
                    .out_bin = out_bin,
                    .writer_metrics_path = writer_metrics_path,
                    .bpe_metrics_path = bpe_metrics_path,
                    .vocab_sha = vocab_sha,
                    .merges_sha = merges_sha,
                    .use_heap_bpe = use_heap_bpe,
                    .hold_worker_start_ms = hold_worker_start_ms,
                    .result = 0,
                };
                count += 1;
            }
            line_start = i + 1;
        }
    }
    count_out.* = count;
    return 0;
}

fn runBatch(ctx: *const Context, batch_list_path: [*:0]const u8, vocab_sha: [*:0]const u8, merges_sha: [*:0]const u8, batch_workers: usize, use_heap_bpe: bool, hold_worker_start_ms: u32, batch_metrics_path: [*:0]const u8) c_int {
    var jobs: [kMaxBatchJobs]BatchJob = undefined;
    var job_count: usize = 0;
    const parse_rc = parseBatchList(batch_list_path, ctx, vocab_sha, merges_sha, jobs[0..], &job_count, use_heap_bpe, hold_worker_start_ms);
    if (parse_rc != 0) return parse_rc;
    if (job_count == 0) return 99;
    if (batch_workers > 0) {
        if (batch_workers > kMaxBatchJobs) return 103;
        var next_index: usize = 0;
        var threads: [kMaxBatchJobs]usize = undefined;
        var args: [kMaxBatchJobs]BatchThreadArg = undefined;
        var worker_count = batch_workers;
        if (worker_count > job_count) worker_count = job_count;
        var wi: usize = 0;
        while (wi < worker_count) : (wi += 1) {
            args[wi] = BatchThreadArg{ .jobs = &jobs, .job_count = job_count, .next_index = &next_index, .ctx = ctx, .use_heap_bpe = use_heap_bpe, .hold_worker_start_ms = hold_worker_start_ms, .jobs_done = 0, .start_ns = 0, .end_ns = 0, .result = 0 };
            if (pthread_create(&threads[wi], null, batchQueueWorker, &args[wi]) != 0) return 100;
        }
        wi = 0;
        while (wi < worker_count) : (wi += 1) {
            if (pthread_join(threads[wi], null) != 0) return 101;
        }
        wi = 0;
        while (wi < worker_count) : (wi += 1) {
            if (args[wi].result != 0) return args[wi].result;
        }
        var ji: usize = 0;
        while (ji < job_count) : (ji += 1) {
            if (jobs[ji].result != 0) return jobs[ji].result;
        }
        if (!writeBatchMetrics(batch_metrics_path, args[0..worker_count], job_count)) return 104;
        return 0;
    }
    var threads: [kMaxBatchJobs]usize = undefined;
    var i: usize = 0;
    while (i < job_count) : (i += 1) {
        if (pthread_create(&threads[i], null, batchWorker, &jobs[i]) != 0) return 100;
    }
    i = 0;
    while (i < job_count) : (i += 1) {
        if (pthread_join(threads[i], null) != 0) return 101;
    }
    i = 0;
    while (i < job_count) : (i += 1) {
        if (jobs[i].result != 0) return jobs[i].result;
    }
    return 0;
}

export fn main(argc: c_int, argv: [*][*:0]u8) c_int {
    var input_path: [*:0]const u8 = "";
    var batch_list_path: [*:0]const u8 = "";
    var tokenizer_dir: [*:0]const u8 = "";
    var out_jsonl: [*:0]const u8 = "";
    var out_bin: [*:0]const u8 = "";
    var vocab_sha: [*:0]const u8 = "unknown";
    var merges_sha: [*:0]const u8 = "unknown";
    var input_format: [*:0]const u8 = "jsonl";
    var table_format: [*:0]const u8 = "tsv";
    var tokenizer_table: [*:0]const u8 = "";
    var writer_metrics_path: [*:0]const u8 = "";
    var bpe_metrics_path: [*:0]const u8 = "";
    var batch_metrics_path: [*:0]const u8 = "";
    var bpe_algorithm: [*:0]const u8 = "repeated_scan";
    var batch_workers: usize = 0;
    var hold_worker_start_ms: u32 = 0;
    var i: c_int = 1;
    while (i < argc) : (i += 1) {
        if (cstrEq(argv[@intCast(i)], "--input")) {
            i += 1;
            input_path = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--batch-list")) {
            i += 1;
            batch_list_path = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--tokenizer-dir")) {
            i += 1;
            tokenizer_dir = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--out-jsonl")) {
            i += 1;
            out_jsonl = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--out-bin")) {
            i += 1;
            out_bin = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--vocab-sha256")) {
            i += 1;
            vocab_sha = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--merges-sha256")) {
            i += 1;
            merges_sha = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--input-format")) {
            i += 1;
            input_format = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--table-format")) {
            i += 1;
            table_format = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--tokenizer-table")) {
            i += 1;
            tokenizer_table = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--writer-metrics")) {
            i += 1;
            writer_metrics_path = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--bpe-metrics")) {
            i += 1;
            bpe_metrics_path = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--batch-metrics")) {
            i += 1;
            batch_metrics_path = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--bpe-algorithm")) {
            i += 1;
            bpe_algorithm = argv[@intCast(i)];
        } else if (cstrEq(argv[@intCast(i)], "--batch-workers")) {
            i += 1;
            batch_workers = parseU32(argv[@intCast(i)][0..cstrLen(argv[@intCast(i)])]) orelse 0;
        } else if (cstrEq(argv[@intCast(i)], "--hold-worker-start-ms")) {
            i += 1;
            hold_worker_start_ms = parseU32(argv[@intCast(i)][0..cstrLen(argv[@intCast(i)])]) orelse 0;
        }
    }
    if ((cstrLen(input_path) == 0 and cstrLen(batch_list_path) == 0) or cstrLen(tokenizer_dir) == 0) return 64;
    if (cstrLen(batch_list_path) == 0 and cstrLen(out_bin) == 0) return 64;

    var ctx = Context{
        .token_entries = undefined,
        .token_cap = 0,
        .token_storage = undefined,
        .token_storage_len = 0,
        .token_storage_cap = 0,
        .merge_entries = undefined,
        .merge_cap = 0,
        .byte_fallback = undefined,
        .audit_allocations = false,
        .audited_allocations = 0,
    };
    var vocab_path_buf: [kMaxPath]u8 = undefined;
    var merges_path_buf: [kMaxPath]u8 = undefined;
    if (cstrEq(table_format, "packed") or cstrEq(table_format, "packed-mmap")) {
        if (cstrLen(tokenizer_table) == 0) return 65;
        if (!loadPackedTable(&ctx, tokenizer_table, cstrEq(table_format, "packed-mmap"))) return 68;
    } else {
        if (!makePath(vocab_path_buf[0..], tokenizer_dir, "vocab.hex.tsv")) return 65;
        if (!makePath(merges_path_buf[0..], tokenizer_dir, "merges.hex.tsv")) return 66;
        if (!loadVocab(&ctx, @ptrCast(&vocab_path_buf))) return 67;
        if (!loadMerges(&ctx, @ptrCast(&merges_path_buf))) return 68;
    }
    if (cstrLen(batch_list_path) != 0) {
        return runBatch(&ctx, batch_list_path, vocab_sha, merges_sha, batch_workers, cstrEq(bpe_algorithm, "heap"), hold_worker_start_ms, batch_metrics_path);
    }
    const binary_input = cstrEq(input_format, "binary");
    var input_len: usize = 0;
    const input = if (binary_input) (mapFileReadOnlyWithAdvice(input_path, &input_len, MADV_SEQUENTIAL) orelse return 69) else (readFile(input_path, &input_len) orelse return 69);
    const valid_count = if (binary_input) (countValidBinaryQa(input[0..input_len]) orelse return 74) else countValidQa(input[0..input_len]);
    const json_enabled = cstrLen(out_jsonl) != 0 and !cstrEq(out_jsonl, "-");
    const json_fd = if (json_enabled) open(out_jsonl, O_CREAT | O_TRUNC | O_WRONLY, 0o600) else -1;
    if (json_enabled and json_fd < 0) return 70;
    const bin_fd = open(out_bin, O_CREAT | O_TRUNC | O_WRONLY, 0o600);
    if (bin_fd < 0) return 71;
    var bin_writer = initBufferedWriter(bin_fd, kDefaultBinBufferBytes) orelse return 73;
    if (!writeHeader(&bin_writer, valid_count, vocab_sha, merges_sha)) return 72;

    var record_id: [1024]u8 = undefined;
    var source_kind: [64]u8 = undefined;
    var question: [kMaxTextBytes]u8 = undefined;
    var answer: [kMaxTextBytes]u8 = undefined;
    var q_tokens: [kMaxTokenCapacity]u32 = undefined;
    var a_tokens: [kMaxTokenCapacity]u32 = undefined;
    var symbols: [kMaxTokenCapacity]u32 = undefined;
    var prev: [kMaxTokenCapacity]usize = undefined;
    var next: [kMaxTokenCapacity]usize = undefined;
    var active: [kMaxTokenCapacity]u8 = undefined;
    var heap: [kMaxTokenCapacity * 3]HeapEntry = undefined;
    var token_ids: [kMaxTokenCapacity * 2]u32 = undefined;
    var processed: u64 = 0;
    var rejected: u64 = 0;
    var total_tokens: u64 = 0;
    var bpe_metrics = initBpeMetrics();
    const bpe_metrics_ptr: ?*BpeMetrics = if (cstrLen(bpe_metrics_path) == 0) null else &bpe_metrics;
    ctx.audit_allocations = true;
    if (binary_input) {
        var offset: usize = 12;
        var seen: u64 = 0;
        while (seen < valid_count) : (seen += 1) {
            const kind_enum = input[offset];
            offset += 1;
            const rid_len = readU16LEMem(input[0..input_len], offset) orelse return 75;
            offset += 2;
            const q_len = readU32LEMem(input[0..input_len], offset) orelse return 76;
            offset += 4;
            const a_len = readU32LEMem(input[0..input_len], offset) orelse return 77;
            offset += 4;
            const rid_start = offset;
            const q_start = rid_start + @as(usize, rid_len);
            const a_start = q_start + @as(usize, q_len);
            const end = a_start + @as(usize, a_len);
            if (end > input_len) return 78;
            const kind_name = sourceKindName(kind_enum);
            const written = encodeAndWriteRecord(&ctx, json_fd, &bin_writer, input[rid_start..q_start], kind_name, input[q_start..a_start], input[a_start..end], q_tokens[0..], a_tokens[0..], symbols[0..], prev[0..], next[0..], active[0..], heap[0..], token_ids[0..], vocab_sha, merges_sha, bpe_metrics_ptr, cstrEq(bpe_algorithm, "heap")) orelse return 80;
            processed += 1;
            total_tokens += written;
            offset = end;
        }
    } else {
        var line_start: usize = 0;
        i = 0;
        while (@as(usize, @intCast(i)) <= input_len) : (i += 1) {
            const pos: usize = @intCast(i);
            if (pos == input_len or input[pos] == '\n') {
                const line = input[line_start..pos];
                const rid_len = extractString(line, "record_id", record_id[0..]);
                const kind_len = extractString(line, "source_kind", source_kind[0..]);
                const q_len = extractString(line, "question", question[0..]);
                const a_len = extractString(line, "answer", answer[0..]);
                if (rid_len == null or kind_len == null or q_len == null or a_len == null or q_len.? == 0 or a_len.? == 0) {
                    rejected += 1;
                    line_start = pos + 1;
                    continue;
                }
                const written = encodeAndWriteRecord(&ctx, json_fd, &bin_writer, record_id[0..rid_len.?], source_kind[0..kind_len.?], question[0..q_len.?], answer[0..a_len.?], q_tokens[0..], a_tokens[0..], symbols[0..], prev[0..], next[0..], active[0..], heap[0..], token_ids[0..], vocab_sha, merges_sha, bpe_metrics_ptr, cstrEq(bpe_algorithm, "heap")) orelse return 82;
                processed += 1;
                total_tokens += written;
                line_start = pos + 1;
            }
        }
    }
    ctx.audit_allocations = false;
    if (json_enabled) _ = close(json_fd);
    if (!flushBufferedWriter(&bin_writer)) return 93;
    _ = close(bin_fd);
    if (!writeWriterMetrics(writer_metrics_path, &bin_writer, kDefaultBinBufferBytes)) return 94;
    if (bpe_metrics_ptr != null and !writeBpeMetrics(bpe_metrics_path, &bpe_metrics, cstrEq(bpe_algorithm, "heap"))) return 102;
    if (processed != valid_count) return 90;
    if (ctx.audited_allocations != 0) return 91;
    if (rejected == 0xffffffffffffffff or total_tokens == 0xffffffffffffffff) return 92;
    return 0;
}
