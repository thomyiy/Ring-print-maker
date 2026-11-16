let cache: any
export default defineEventHandler(async () => (cache ??= await lancerMoteur(['schema'])))
