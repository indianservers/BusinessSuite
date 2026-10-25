import '../core/api_client.dart';
import '../core/models.dart';

class PmsRepository {
  PmsRepository(this.api);
  final ApiClient api;
  static const base = '/project-management';
  Future<SessionUser> me() async =>
      SessionUser.fromJson(await api.request('GET', '/auth/me') as Json);
  Future<List<Workspace>> workspaces() async =>
      (await api.request('GET', '$base/workspaces') as List)
          .map((e) => Workspace.fromJson(e as Json))
          .toList();
  Future<Overview> overview(int id) async => Overview.fromJson(
    await api.request('GET', '$base/workspaces/$id/overview') as Json,
  );
  Future<void> createWorkspace(String name) =>
      api.request('POST', '$base/workspaces', data: {'name': name});
  Future<void> createProject(int workspaceId, String name, String key) =>
      api.request(
        'POST',
        '$base/projects',
        data: {'workspace_id': workspaceId, 'name': name, 'project_key': key},
      );
  Future<void> createTask(
    int projectId, {
    required String title,
    required String key,
    required String description,
    required String priority,
  }) => api.request(
    'POST',
    '$base/projects/$projectId/tasks',
    data: {
      'title': title,
      'task_key': key,
      'description': description,
      'priority': priority,
      'status': 'To Do',
    },
  );
  Future<void> setStatus(int taskId, String status) =>
      api.request('PATCH', '$base/tasks/$taskId', data: {'status': status});
  Future<WorkTask> task(int id) async =>
      WorkTask.fromJson(await api.request('GET', '$base/tasks/$id') as Json);
  Future<List<Json>> members(int workspaceId) async =>
      (await api.request('GET', '$base/workspaces/$workspaceId/members')
              as List)
          .cast<Json>();
  Future<List<Json>> invitations(int workspaceId) async =>
      (await api.request('GET', '$base/workspaces/$workspaceId/invitations')
              as List)
          .cast<Json>();
  Future<Json> invite(int workspaceId, String email, String role) async =>
      await api.request(
            'POST',
            '$base/workspaces/$workspaceId/invitations',
            data: {'email': email, 'role': role},
          )
          as Json;
  Future<void> revokeInvitation(int workspaceId, int id) =>
      api.request('DELETE', '$base/workspaces/$workspaceId/invitations/$id');
  Future<void> changeMemberRole(int workspaceId, int id, String role) =>
      api.request(
        'PATCH',
        '$base/workspaces/$workspaceId/members/$id',
        data: {'role': role},
      );
  Future<void> removeMember(int workspaceId, int id) =>
      api.request('DELETE', '$base/workspaces/$workspaceId/members/$id');
  Future<int> acceptInvitation(String token) async =>
      (await api.request(
                'POST',
                '$base/workspace-invitations/accept',
                data: {'token': token},
              )
              as Json)['workspace_id']
          as int;
}
