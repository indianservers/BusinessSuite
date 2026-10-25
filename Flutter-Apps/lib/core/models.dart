typedef Json = Map<String, dynamic>;

class Workspace {
  const Workspace(this.id, this.name, this.role);
  factory Workspace.fromJson(Json json) => Workspace(
    json['id'] as int,
    json['name'] as String,
    json['role'] as String,
  );
  final int id;
  final String name;
  final String role;
  bool get canEdit => const {'Owner', 'Admin', 'Member'}.contains(role);
  bool get canManage => const {'Owner', 'Admin'}.contains(role);
}

class Project {
  const Project(this.id, this.name, this.key);
  factory Project.fromJson(Json json) => Project(
    json['id'] as int,
    json['name'] as String,
    json['project_key'] as String,
  );
  final int id;
  final String name;
  final String key;
}

class WorkTask {
  const WorkTask({
    required this.id,
    required this.projectId,
    required this.key,
    required this.title,
    required this.status,
    required this.priority,
    this.description = '',
    this.dueDate,
  });
  factory WorkTask.fromJson(Json json) => WorkTask(
    id: json['id'] as int,
    projectId: json['project_id'] as int,
    key: json['task_key'] as String,
    title: json['title'] as String,
    status: json['status'] as String,
    priority: json['priority'] as String,
    description: json['description'] as String? ?? '',
    dueDate: json['due_date'] as String?,
  );
  final int id;
  final int projectId;
  final String key, title, status, priority, description;
  final String? dueDate;
  bool get isDone =>
      const {'Done', 'Completed', 'Closed', 'Resolved'}.contains(status);
}

class Overview {
  Overview.fromJson(Json json)
    : role = json['role'] as String,
      projects = (json['projects'] as List)
          .map((e) => Project.fromJson(e as Json))
          .toList(),
      tasks = (json['tasks'] as List)
          .map((e) => WorkTask.fromJson(e as Json))
          .toList();
  final String role;
  final List<Project> projects;
  final List<WorkTask> tasks;
}

class SessionUser {
  SessionUser.fromJson(Json json)
    : id = json['id'] as int?,
      email = json['email'] as String,
      role = (json['role'] as Json?)?['name'] as String? ?? 'User',
      permissions = ((json['role'] as Json?)?['permissions'] as List? ?? [])
          .map((e) => (e as Json)['name'] as String)
          .toSet(),
      isSuperuser = json['is_superuser'] == true;
  final String email, role;
  final int? id;
  final Set<String> permissions;
  final bool isSuperuser;
  bool get canCreateWorkspace =>
      isSuperuser ||
      permissions.intersection({'pms_manage_projects', 'pms_admin'}).isNotEmpty;
}
