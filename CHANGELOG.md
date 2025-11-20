# Changelog

## [2.0.0](https://github.com/GDC-ConsumerEdge/parameter-store/compare/v1.2.1...v2.0.0) (2025-11-20)


### ⚠ BREAKING CHANGES

* add changeset models ([#83](https://github.com/GDC-ConsumerEdge/parameter-store/issues/83))

### Features

* Add ability to create/modify ChangeSets from object creation pages ([4b1ff83](https://github.com/GDC-ConsumerEdge/parameter-store/commit/4b1ff838cd6dda5b9a86961f9179eeb202dc5e1a))
* add changeset interception for top-level entities ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* add changeset interception for top-level entities ([#92](https://github.com/GDC-ConsumerEdge/parameter-store/issues/92)) ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* add changeset models ([#83](https://github.com/GDC-ConsumerEdge/parameter-store/issues/83)) ([4734e6c](https://github.com/GDC-ConsumerEdge/parameter-store/commit/4734e6ccc23a46f4a925a81cdbeeb3601f38dda4))
* add interception of saving for TLEs ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* add support for a visual indicator of the active ChangeSet ([#101](https://github.com/GDC-ConsumerEdge/parameter-store/issues/101)) ([cb53deb](https://github.com/GDC-ConsumerEdge/parameter-store/commit/cb53deb4dc9f2a09082c51ed3a3066529e9c5ded))
* **changesets:** add initial support for changeset management through the UI ([9f5d484](https://github.com/GDC-ConsumerEdge/parameter-store/commit/9f5d48476a8cde063511951572b64f4070c8bf48))
* **changesets:** Add initial support for management of ChangeSets through the Admin UI ([4b1ff83](https://github.com/GDC-ConsumerEdge/parameter-store/commit/4b1ff838cd6dda5b9a86961f9179eeb202dc5e1a))
* Implement ChangeSet Management in Django Admin ([#90](https://github.com/GDC-ConsumerEdge/parameter-store/issues/90)) ([9f5d484](https://github.com/GDC-ConsumerEdge/parameter-store/commit/9f5d48476a8cde063511951572b64f4070c8bf48))
* initial support for the addition and display of ChangeSets in the Admin UI ([#88](https://github.com/GDC-ConsumerEdge/parameter-store/issues/88)) ([4b1ff83](https://github.com/GDC-ConsumerEdge/parameter-store/commit/4b1ff838cd6dda5b9a86961f9179eeb202dc5e1a))
* update the visual appearance of the sidebar ([594d348](https://github.com/GDC-ConsumerEdge/parameter-store/commit/594d348ba6d6fc57c63ecf36952866d6b810becf))


### Bug Fixes

* **admin:** ensure new entities are created as drafts ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* bug where updating a group would incorrectly fail to create a draft and would persist draft changes to live objects ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* changeset actions logic and object deletion logic when deleting a changeset ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* changeset selector works; rendering in UI improved ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* **changesets:** changeset name now a required field ([4b1ff83](https://github.com/GDC-ConsumerEdge/parameter-store/commit/4b1ff838cd6dda5b9a86961f9179eeb202dc5e1a))
* **changesets:** correct changeset button link ([4b1ff83](https://github.com/GDC-ConsumerEdge/parameter-store/commit/4b1ff838cd6dda5b9a86961f9179eeb202dc5e1a))
* **changesets:** correct comment ([9f5d484](https://github.com/GDC-ConsumerEdge/parameter-store/commit/9f5d48476a8cde063511951572b64f4070c8bf48))
* **changesets:** fix menu dropdown behavior, now selecting draft changesets ([9f5d484](https://github.com/GDC-ConsumerEdge/parameter-store/commit/9f5d48476a8cde063511951572b64f4070c8bf48))
* constraints, logic for deleting drafts, and update changeset actions based on new columns and constraints ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* draft clusters can only see draft groups within the same changeset ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* ensure all views use 'Parameter Store' ([#94](https://github.com/GDC-ConsumerEdge/parameter-store/issues/94)) ([091c03e](https://github.com/GDC-ConsumerEdge/parameter-store/commit/091c03e121c21609f523dc52c97a8f740cc11378))
* ensure changeset dropdown supports dark theme ([9f5d484](https://github.com/GDC-ConsumerEdge/parameter-store/commit/9f5d48476a8cde063511951572b64f4070c8bf48))
* ensure optimal query perf for clusters; fix readonly fields for top-level entities ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* group interception was failing; fix and add tests ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* optimize queries in cluster view with new related objects ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))
* swap the order of template engines to preference the Django engine ([9f5d484](https://github.com/GDC-ConsumerEdge/parameter-store/commit/9f5d48476a8cde063511951572b64f4070c8bf48))
* update changeset-aware entities to default to is_live=False ([#89](https://github.com/GDC-ConsumerEdge/parameter-store/issues/89)) ([ea87538](https://github.com/GDC-ConsumerEdge/parameter-store/commit/ea8753889d7a02406f760d84a836867091b8bf5b))
* update deps ([#91](https://github.com/GDC-ConsumerEdge/parameter-store/issues/91)) ([ade1712](https://github.com/GDC-ConsumerEdge/parameter-store/commit/ade1712edc6b5d7ba317d05db9945ced391f0640))


### Documentation

* add changesets tdd ([#93](https://github.com/GDC-ConsumerEdge/parameter-store/issues/93)) ([86747d6](https://github.com/GDC-ConsumerEdge/parameter-store/commit/86747d64d6d411d970a0994de64895029ce57374))
* add docstrings to new functions ([9f5d484](https://github.com/GDC-ConsumerEdge/parameter-store/commit/9f5d48476a8cde063511951572b64f4070c8bf48))
* update all references of Edge Parameter Store to Parameter Store only, but retain the EPS acronym ([091c03e](https://github.com/GDC-ConsumerEdge/parameter-store/commit/091c03e121c21609f523dc52c97a8f740cc11378))
* update README.md ([40411b7](https://github.com/GDC-ConsumerEdge/parameter-store/commit/40411b7f3e91ac96b1a609e0659c63fd0fa7a9f8))

## [1.2.1](https://github.com/GDC-ConsumerEdge/parameter-store/compare/v1.2.0...v1.2.1) (2025-09-03)


### Bug Fixes

* **build:** update cloudbuild.yaml ([#82](https://github.com/GDC-ConsumerEdge/parameter-store/issues/82)) ([5c89419](https://github.com/GDC-ConsumerEdge/parameter-store/commit/5c89419c0d2776bb7a8a58dde67b98ac0f5e387a))
* **django:** fix missing models in django makemigrations ([0c74a90](https://github.com/GDC-ConsumerEdge/parameter-store/commit/0c74a9079294b409cae192322a4be8e84ca0e14a))
* fix missing models in django makemigrations and update README for new environment setup ([#81](https://github.com/GDC-ConsumerEdge/parameter-store/issues/81)) ([0c74a90](https://github.com/GDC-ConsumerEdge/parameter-store/commit/0c74a9079294b409cae192322a4be8e84ca0e14a))
* **readme:** fix documentation related to local environment setup ([0c74a90](https://github.com/GDC-ConsumerEdge/parameter-store/commit/0c74a9079294b409cae192322a4be8e84ca0e14a))
* **readme:** fix documentation related to local environment setup ([0c74a90](https://github.com/GDC-ConsumerEdge/parameter-store/commit/0c74a9079294b409cae192322a4be8e84ca0e14a))
* **tests, deps:** add Ruff + upgrade deps ([#77](https://github.com/GDC-ConsumerEdge/parameter-store/issues/77)) ([ae00284](https://github.com/GDC-ConsumerEdge/parameter-store/commit/ae002849947694cadf5f7e77b55643df138f1d1b))


### Documentation

* add infrastructure overview ([#73](https://github.com/GDC-ConsumerEdge/parameter-store/issues/73)) ([5cb661b](https://github.com/GDC-ConsumerEdge/parameter-store/commit/5cb661b6693df4b10cb1083dbd519ed093e49b72))
* add user journey documentation ([#71](https://github.com/GDC-ConsumerEdge/parameter-store/issues/71)) ([3741670](https://github.com/GDC-ConsumerEdge/parameter-store/commit/3741670014c2e6c4907ee23b0caf5cb6d6ddd31f))

## [1.2.0](https://github.com/GDC-ConsumerEdge/parameter-store/compare/v1.1.0...v1.2.0) (2025-05-22)


### Features

* [eps-integrations] add ability to merge csv for cluster-registry sot files ([#61](https://github.com/GDC-ConsumerEdge/parameter-store/issues/61)) ([0172933](https://github.com/GDC-ConsumerEdge/parameter-store/commit/0172933f74e1f1dc224325f282931c085e4f5b38))
* add eps_to_csv_converter utility ([#37](https://github.com/GDC-ConsumerEdge/parameter-store/issues/37)) ([ba6018e](https://github.com/GDC-ConsumerEdge/parameter-store/commit/ba6018ed0206eefceabd7c66b3d602ab722f4358))
* add GH Actions integration workflow examples for HRM and cluster provisioner ([#56](https://github.com/GDC-ConsumerEdge/parameter-store/issues/56)) ([c897127](https://github.com/GDC-ConsumerEdge/parameter-store/commit/c89712740d2693ea7a582d5bdf7b2e34032d814e))

## [1.1.0](https://github.com/GDC-ConsumerEdge/parameter-store/compare/v1.0.0...v1.1.0) (2025-04-18)


### Features

* add API endpoints to get a single group or cluster by name ([075e9bb](https://github.com/GDC-ConsumerEdge/parameter-store/commit/075e9bbef02607c7bc7d92a0e763c869c2272a29))
* add customized colors and logo as site icon / favicons ([#13](https://github.com/GDC-ConsumerEdge/parameter-store/issues/13)) ([ed66f2f](https://github.com/GDC-ConsumerEdge/parameter-store/commit/ed66f2ff00c8a4eb5091815f4702aa23899ffb22))
* add data loader script and pipeline ([1ef0979](https://github.com/GDC-ConsumerEdge/parameter-store/commit/1ef0979d341fd5d4278ef1f1828c438d5ac1a4a0))
* add secondary groups for clusters and group custom data ([#36](https://github.com/GDC-ConsumerEdge/parameter-store/issues/36)) ([075e9bb](https://github.com/GDC-ConsumerEdge/parameter-store/commit/075e9bbef02607c7bc7d92a0e763c869c2272a29))
* add updated_at to all models ([#31](https://github.com/GDC-ConsumerEdge/parameter-store/issues/31)) ([2c898f5](https://github.com/GDC-ConsumerEdge/parameter-store/commit/2c898f5d70c295cdb2d2b4e91ab299e7382515de))
* allow server time zone to be set by environment variable `TIME_ZONE` ([2c898f5](https://github.com/GDC-ConsumerEdge/parameter-store/commit/2c898f5d70c295cdb2d2b4e91ab299e7382515de))
* group downstream custom data changes propagate to updated_at field in object and are output via API ([075e9bb](https://github.com/GDC-ConsumerEdge/parameter-store/commit/075e9bbef02607c7bc7d92a0e763c869c2272a29))
* hide tables from UI for cluster-related data; fixes [#40](https://github.com/GDC-ConsumerEdge/parameter-store/issues/40) ([075e9bb](https://github.com/GDC-ConsumerEdge/parameter-store/commit/075e9bbef02607c7bc7d92a0e763c869c2272a29))
* update cluster secondary groups and tags to make them optional when creating new objects ([#46](https://github.com/GDC-ConsumerEdge/parameter-store/issues/46)) ([bf12b4d](https://github.com/GDC-ConsumerEdge/parameter-store/commit/bf12b4d6b76ad57505025166216c5bbaace7d79c))
* update ClusterIntent models ([2bb2e37](https://github.com/GDC-ConsumerEdge/parameter-store/commit/2bb2e3771bcbc7522e981b8b607f01443e129705))


### Bug Fixes

* CustomAdminSite gets proper site headers and titles in admin UI ([2c898f5](https://github.com/GDC-ConsumerEdge/parameter-store/commit/2c898f5d70c295cdb2d2b4e91ab299e7382515de))
* missing model from example data loader ([#43](https://github.com/GDC-ConsumerEdge/parameter-store/issues/43)) ([5904342](https://github.com/GDC-ConsumerEdge/parameter-store/commit/590434233f3ce6db27817a048f5e7d04b48feef5))
* **terraform:** corrects destroy behavior ([5904342](https://github.com/GDC-ConsumerEdge/parameter-store/commit/590434233f3ce6db27817a048f5e7d04b48feef5))
* validator assignments in UI show correct model field pre-selected ([#35](https://github.com/GDC-ConsumerEdge/parameter-store/issues/35)) ([52d18f2](https://github.com/GDC-ConsumerEdge/parameter-store/commit/52d18f215b44782ca41b995bde78948b2ad82f80))

## 1.0.0 (2025-04-01)


### Documentation

* significantly update README ([#9](https://github.com/GDC-ConsumerEdge/parameter-store/issues/9)) ([b227ed0](https://github.com/GDC-ConsumerEdge/parameter-store/commit/b227ed04ba262edafcd572ee707dc900ff27cee3))


### Miscellaneous Chores

* release 1.0.0 ([d42cd99](https://github.com/GDC-ConsumerEdge/parameter-store/commit/d42cd9987e559c987665b650ab30b1f9b5dce4e7))

## Changelog
