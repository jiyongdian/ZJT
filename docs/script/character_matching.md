# 剧本解析角色匹配功能

## 更新日期
- 2026年6月9日：新增角色数据库匹配功能
- 2026年6月9日：修复前端未使用 db_character_info 的问题
- 2026年6月9日：修复角色名称不一致问题（LLM名称 vs 数据库名称）

## 问题背景

在剧本解析过程中，LLM 会根据剧本文字自行生成角色名称（如"布冯"、"C罗"、"梅西"），但数据库中的角色名称可能是不同格式（如"阿方索戴维斯_AlphonsoDavies"）。这导致解析出的角色无法与数据库中的角色正确关联。

**根本原因**：`script_parser.py` 中加载了数据库场景和道具列表传给 LLM 做匹配，但没有加载数据库角色列表。

## 解决方案

### 1. 加载数据库角色列表

在 `llm/script_parser.py` 中，新增加载数据库角色的逻辑：

```python
# 获取数据库中的角色列表（如果提供了world_id）
db_characters_text = ""
if world_id is not None:
    from model.character import CharacterModel
    characters_result = CharacterModel.list_by_world(world_id=world_id, page=1, page_size=50)
    db_characters = characters_result.get('data', []) if characters_result else []
    
    if db_characters:
        char_lines = []
        for char in db_characters:
            char_desc = char.get('identity', '') or char.get('appearance', '') or char.get('personality', '无')
            char_lines.append(f"- ID: {char['id']}, 名称: {char['name']}, 描述: {char_desc}")
        
        db_characters_text = f"""
**【数据库已有角色列表】**
以下是数据库中已存在的角色（最多50个），如果剧本中的角色与数据库中的角色相同或相似，请在返回的character对象中设置character_db_id字段为对应的数据库角色ID：
...
"""
```

### 2. 更新 LLM Prompt

在系统提示词中添加角色匹配规则：

```
8. **角色与数据库关联**：每个character必须包含character_db_id字段
   - 如果剧本中的角色与数据库中已有角色匹配，则将character_db_id设置为数据库角色的ID
   - 如果是新角色，不在数据库中，则character_db_id必须设置为null
   - 匹配时考虑角色名称和描述的相似性，不需要完全一致
   - **【警告】严禁编造不存在的character_db_id**
```

在用户提示词中添加数据库角色列表：

```
数据库中的角色列表：
```{db_characters_text} ```
```

更新 JSON 格式示例，添加 `character_db_id` 字段：

```json
"characters": [
    {
      "id": "char_001",
      "name": "人物名称",
      "character_db_id": 123,
      "role": "主角/配角/群演",
      "description": "外貌和特征描述",
      "gender": "男/女",
      "age_range": "年龄范围"
    }
]
```

### 3. 服务端后处理

在 `server.py` 中添加角色匹配后处理函数：

```python
def _match_character_to_db(character_id: str, characters: list) -> tuple:
    """
    匹配角色到数据库
    
    Returns:
        (db_character_id, reference_image, character_name) 元组
    """
    char_map = {c['id']: c for c in characters}
    current_char = char_map.get(character_id)
    
    if not current_char:
        return (None, None, None)
    
    db_id = current_char.get('character_db_id')
    if db_id is not None:
        from model.character import CharacterModel
        db_character = CharacterModel.get_by_id(db_id)
        if db_character:
            return (db_id, db_character.reference_image, db_character.name)
    
    return (None, None, None)
```

在 `parse_script` 接口中添加后处理：

```python
# 为每个shot中的characters_present添加db_character信息
characters = parsed_data.get('characters', [])
for group in shot_groups:
    shots = group.get('shots', [])
    for shot in shots:
        characters_present = shot.get('characters_present', [])
        db_character_info = []
        for char_id in characters_present:
            db_char_id, db_char_pic, db_char_name = _match_character_to_db(char_id, characters)
            db_character_info.append({
                'character_id': char_id,
                'db_character_id': db_char_id,
                'db_character_pic': db_char_pic,
                'db_character_name': db_char_name
            })
        shot['db_character_info'] = db_character_info
```

## 数据流

```
剧本内容
    ↓
script_parser.py
    ↓
加载数据库角色列表 (CharacterModel.list_by_world)
    ↓
格式化为文本传给 LLM
    ↓
LLM 解析剧本，生成 characters 数组（包含 character_db_id）
    ↓
server.py 后处理
    ↓
匹配 character_db_id 到数据库角色
    ↓
返回 db_character_info（包含 db_character_id, db_character_pic, db_character_name）
```

## 返回数据示例

```json
{
  "code": 0,
  "message": "解析成功",
  "data": {
    "characters": [
      {
        "id": "char_001",
        "name": "布冯",
        "character_db_id": 4651,
        "role": "主角",
        "description": "...",
        "gender": "男",
        "age_range": "45-50"
      }
    ],
    "shot_groups": [
      {
        "group_id": "grp_001",
        "group_name": "米兰公寓开场",
        "shots": [
          {
            "shot_id": "s001",
            "characters_present": ["char_001"],
            "db_character_info": [
              {
                "character_id": "char_001",
                "db_character_id": 4651,
                "db_character_pic": "http://...",
                "db_character_name": "阿方索戴维斯_AlphonsoDavies"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

## 与场景/道具匹配的对比

| 数据类型 | DB加载 | LLM匹配字段 | 后处理函数 | 返回字段 |
|---------|--------|------------|-----------|---------|
| 场景(Location) | ✅ `LocationModel.get_tree_by_world` | `location_db_id` | `_match_location_to_db` | `db_location_id`, `db_location_pic`, `location_name` |
| 道具(Props) | ✅ `PropsModel.list_by_world` | `props_db_id` | 无 | 无 |
| **角色(Character)** | ✅ `CharacterModel.list_by_world` | `character_db_id` | `_match_character_to_db` | `db_character_info` |

## 前端实现

### 问题描述

原来的前端实现存在以下问题：
1. 完全忽略后端返回的 `db_character_info`
2. 只从提示词文本中提取 `【【角色名】】` 模式
3. 通过精确名称匹配 `state.worldCharacters`，如果名称不匹配则无法关联

### 解决方案

在 `web/js/nodes.js` 中修改了角色匹配逻辑：

**1. 新增 `getCharactersFromDbInfo()` 函数**

优先使用后端返回的 `db_character_info` 匹配角色：

```javascript
function getCharactersFromDbInfo() {
  const shotJson = node.data.shotJson || {};
  const dbCharInfo = shotJson.db_character_info;
  if(!dbCharInfo || !Array.isArray(dbCharInfo) || dbCharInfo.length === 0) {
    return null;
  }

  const worldChars = state.worldCharacters || [];
  const matchedNames = [];

  dbCharInfo.forEach(info => {
    if(info.db_character_id && info.db_character_name) {
      // 后端已匹配到数据库角色，使用 db_character_name
      if(!matchedNames.includes(info.db_character_name)) {
        matchedNames.push(info.db_character_name);
      }
    } else if(info.character_id) {
      // 后端未匹配到，尝试从 scriptData.characters 中查找名称
      const scriptData = node.data.shotJson?.scriptData || {};
      const characters = scriptData.characters || [];
      const charObj = characters.find(c => c.id === info.character_id);
      if(charObj && charObj.name) {
        const existsInWorld = worldChars.some(wc => wc.name === charObj.name);
        if(existsInWorld && !matchedNames.includes(charObj.name)) {
          matchedNames.push(charObj.name);
        }
      }
    }
  });

  return matchedNames.length > 0 ? matchedNames : null;
}
```

**2. 修改初始匹配逻辑**

```javascript
// 优先使用 db_character_info，否则从提示词提取
const dbMatchedChars = getCharactersFromDbInfo();
if(dbMatchedChars) {
  node.data.refCharacters = dbMatchedChars;
} else {
  const initMode = node.data.videoMode || 'first_last_frame';
  const initPromptSource = initMode === 'multi_reference'
    ? (node.data.videoPromptText || node.data.videoPrompt || '')
    : (node.data.imagePrompt || '');
  node.data.refCharacters = extractCharacterNames(initPromptSource);
}
```

**3. 修改 `updateShotReferences()` 函数**

确保刷新引用时也优先使用 `db_character_info`：

```javascript
function updateShotReferences() {
  // 重新匹配角色：优先使用 db_character_info，否则从提示词提取
  const dbMatchedChars = getCharactersFromDbInfo();
  if(dbMatchedChars) {
    node.data.refCharacters = dbMatchedChars;
  } else {
    const mode = node.data.videoMode || 'first_last_frame';
    const promptSource = mode === 'multi_reference'
      ? (node.data.videoPromptText || node.data.videoPrompt || '')
      : (node.data.imagePrompt || '');
    node.data.refCharacters = extractCharacterNames(promptSource);
  }
  renderSceneTags();
  renderPropTags();
  renderCharTags();
}
```

### 匹配流程

```
shotJson.db_character_info
    ↓
检查 db_character_id 和 db_character_name
    ↓
如果存在 → 直接使用 db_character_name
    ↓
如果不存在 → 从 scriptData.characters 查找名称
    ↓
匹配 state.worldCharacters（按名称）
    ↓
渲染角色标签
```

## 角色名称一致性修复

### 问题描述

LLM 生成的角色名称（如"布冯"）与数据库中的实际名称（如"阿方索戴维斯_AlphonsoDavies"）不一致，导致：
1. 前端无法通过名称匹配到 `state.worldCharacters`
2. 角色标签显示不正确

### 解决方案

#### 1. LLM Prompt 优化

在 `llm/script_parser.py` 的系统提示词中添加要求：

```
8. **角色与数据库关联**：每个character必须包含character_db_id字段
   - **【重要】当角色与数据库匹配时，name字段必须使用数据库中的角色名称**
   - 例如：如果数据库中角色名称是"阿方索戴维斯_AlphonsoDavies"，则 name 使用此名称
```

在用户提示词中添加要求：

```
6. **角色名称格式要求**：
   - **【极其重要】当角色与数据库匹配时（character_db_id不为null），【【角色名】】必须使用数据库中的角色名称**
   - 例如：使用"【【阿方索戴维斯_AlphonsoDavies】】"，而不是"【【布冯】】"
```

#### 2. 后端名称替换

在 `server.py` 的后处理中，将 LLM 生成的 `name` 替换为数据库名称：

```python
# 将LLM生成的角色名称替换为数据库中的实际名称
for char in characters:
    db_id = char.get('character_db_id')
    if db_id is not None:
        try:
            from model.character import CharacterModel
            db_character = CharacterModel.get_by_id(db_id)
            if db_character:
                # 保存LLM生成的名称作为备用
                char['llm_name'] = char.get('name')
                # 替换为数据库中的实际名称
                char['name'] = db_character.name
        except Exception as e:
            logger.warning(f"Failed to get character name for {db_id}: {e}")
```

### 修复后的数据流

```
剧本内容："布冯瘫在沙发里..."
    ↓
LLM 解析
    ↓
生成 characters: [{ id: "char_001", name: "布冯", character_db_id: 4649 }]
    ↓
后端处理
    ↓
查询数据库: CharacterModel.get_by_id(4649)
    ↓
替换名称: name = "阿方索戴维斯_AlphonsoDavies"
    ↓
保存备用: llm_name = "布冯"
    ↓
返回: [{ id: "char_001", name: "阿方索戴维斯_AlphonsoDavies", llm_name: "布冯", character_db_id: 4649 }]
```

## 注意事项

1. **角色名称格式**：系统现在会自动将 LLM 生成的名称替换为数据库中的实际名称
2. **新角色处理**：如果剧本中的角色在数据库中不存在，`character_db_id` 为 `null`，`name` 使用 LLM 生成的名称
3. **匹配精度**：匹配基于 LLM 的判断，可能存在误匹配，建议在前端提供手动修正功能
4. **性能考虑**：最多加载 50 个数据库角色，如果角色数量更多，可能需要分页加载
5. **名称备份**：LLM 生成的名称保存在 `llm_name` 字段中，便于调试和回溯
