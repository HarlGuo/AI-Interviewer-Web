-- Enforce manual approval inside Postgres, not only in the web UI or API.

create or replace function public.is_current_user_approved()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.profiles
    where user_id = (select auth.uid())
      and account_status = 'approved'
  );
$$;

revoke all on function public.is_current_user_approved() from public, anon;
grant execute on function public.is_current_user_approved() to authenticated;

drop policy if exists resumes_owner_all on public.resumes;
create policy resumes_approved_owner_all on public.resumes for all to authenticated
using ((select auth.uid()) = user_id and (select public.is_current_user_approved()))
with check ((select auth.uid()) = user_id and (select public.is_current_user_approved()));

drop policy if exists target_roles_owner_all on public.target_roles;
create policy target_roles_approved_owner_all on public.target_roles for all to authenticated
using ((select auth.uid()) = user_id and (select public.is_current_user_approved()))
with check ((select auth.uid()) = user_id and (select public.is_current_user_approved()));

drop policy if exists interviews_owner_all on public.interviews;
create policy interviews_approved_owner_all on public.interviews for all to authenticated
using ((select auth.uid()) = user_id and (select public.is_current_user_approved()))
with check ((select auth.uid()) = user_id and (select public.is_current_user_approved()));

drop policy if exists questions_owner_all on public.interview_questions;
create policy questions_approved_owner_all on public.interview_questions for all to authenticated
using ((select auth.uid()) = user_id and (select public.is_current_user_approved()))
with check ((select auth.uid()) = user_id and (select public.is_current_user_approved()));

drop policy if exists answers_owner_all on public.interview_answers;
create policy answers_approved_owner_all on public.interview_answers for all to authenticated
using ((select auth.uid()) = user_id and (select public.is_current_user_approved()))
with check ((select auth.uid()) = user_id and (select public.is_current_user_approved()));

drop policy if exists reports_owner_select on public.interview_reports;
create policy reports_approved_owner_select on public.interview_reports for select to authenticated
using ((select auth.uid()) = user_id and (select public.is_current_user_approved()));

drop policy if exists usage_owner_select on public.ai_usage_events;
create policy usage_approved_owner_select on public.ai_usage_events for select to authenticated
using ((select auth.uid()) = user_id and (select public.is_current_user_approved()));

drop policy if exists resume_files_owner_select on storage.objects;
drop policy if exists resume_files_owner_insert on storage.objects;
drop policy if exists resume_files_owner_update on storage.objects;
drop policy if exists resume_files_owner_delete on storage.objects;

create policy resume_files_approved_owner_select on storage.objects for select to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text and (select public.is_current_user_approved()));
create policy resume_files_approved_owner_insert on storage.objects for insert to authenticated
with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text and (select public.is_current_user_approved()));
create policy resume_files_approved_owner_update on storage.objects for update to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text and (select public.is_current_user_approved()))
with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text and (select public.is_current_user_approved()));
create policy resume_files_approved_owner_delete on storage.objects for delete to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text and (select public.is_current_user_approved()));
