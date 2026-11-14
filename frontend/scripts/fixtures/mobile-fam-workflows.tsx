import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {useAuthStore} from '../../src/store/authStore';
import '../../src/index.css';
const params=new URLSearchParams(location.search),readonly=params.has('readonly'),limited=params.has('limited');
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'finance@example.test',role:'fam_accountant',is_superuser:false,access:{managed:true,companyId:1,memberships:[1],isAccessAdmin:false,isGlobalAdmin:false,modules:[{key:'fam',route:'/fam',label:'Finance'}],grants:{fam:{enabled:true,role:'fam_accountant',scope:'company',actions:readonly?['view']:['view','create','edit','export'],permissions:readonly?[]:limited?['fam_banking_manage']:['fam_banking_manage','fam_vouchers_post','fam_bank_reconcile',...(params.has('locks')?['fam_settings_manage']:[]),...(params.has('uae')?['fam_settings_manage',...(!params.has('configure-only')?['fam_gst_return_prepare']:[])]:[]),...(params.has('recurring')?['fam_purchase_manage',...(!params.has('bill-only')?['fam_expense_manage']:[])]:[])]}}}}});
// Mirror production route splitting: only compile the page under test.
const Page=(await (params.has('uae')?import('../../src/apps/fam/UAETaxPage'):params.has('recurring')?import('../../src/apps/fam/RecurringPurchasesPage'):params.has('locks')?import('../../src/apps/fam/TransactionLocksPage'):params.has('rules')?import('../../src/apps/fam/BankRulesPage'):import('../../src/apps/fam/FinancialStatementsPage'))).default;
const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
if(params.has('cached-bank')){
  // These envelopes are cached by the bank-account and statement pages before navigation.
  client.setQueryData(['fam','bankAccounts'],{items:[{id:1,bank_name:'Business bank',account_number_masked:'XXXX1234'}]});
  client.setQueryData(['fam','bankStatements'],{items:[{id:8,bank_account_id:1,imported_file_name:'November statement.csv'}]});
}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/fam/'+(params.has('uae')?'uae-tax':params.has('recurring')?'recurring-purchases':params.has('locks')?'transaction-locking':params.has('rules')?'bank-rules':'financial-statements')]}><main style={{padding:12}}><Page/></main></MemoryRouter></QueryClientProvider>);
