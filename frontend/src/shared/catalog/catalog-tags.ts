export function parseCatalogTags(text:string):string[]{
  const tags=[...new Set(text.split(",").map(value=>value.trim().toLowerCase()).filter(Boolean))];
  if(tags.length>20||tags.some(tag=>tag.length>40))throw new Error("Use up to 20 tags, each 40 characters or fewer.");
  return tags;
}
