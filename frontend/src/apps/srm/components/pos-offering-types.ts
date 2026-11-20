export const posOfferingTabs = ['All','Products','Services','Memberships','Subscriptions','Bundles'] as const;
export function matchesOfferingTab(item:{kind:string},tab:string){
 return tab==='All'||item.kind===tab||(tab==='Products'&&item.kind==='Packages');
}
