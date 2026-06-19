---
title: "一、NFT创作与铸造"
type: docs
weight: 1
---

## 一、NFT创作与铸造

NFT（Non-Fungible Token，非同质化代币）是区块链上独一无二的数字资产凭证。与比特币、以太坊等同质化代币（1个BTC永远等于1个BTC）不同，每个NFT都有独立的链上身份，不可互换。理解NFT的技术本质，是创作者进入这个领域的第一课。

本章从技术原理出发，覆盖创作准备、铸造实操、定价策略、智能合约设计、版权保护和常见陷阱，帮助你从零开始建立完整的NFT创作能力。

### 1.1 NFT技术基础

#### 1.1.1 核心标准

NFT的底层是智能合约，主流标准有两个：

| 标准 | 定义 | 特点 | 典型应用 |
|------|------|------|----------|
| ERC-721 | 以太坊首个NFT标准（2018年） | 每个Token有独立tokenId，一对一映射 | CryptoPunks、BAYC |
| ERC-1155 | 多代币标准（Enjin提出） | 单合约支持同质化+非同质化代币，批量铸造Gas降低60-90% | 游戏道具、版画系列 |
| SPL Token | Solana原生NFT标准 | 交易速度快（<1秒），Gas极低 | Magic Eden上的项目 |

理解标准差异直接影响你的铸造决策：单件艺术品用ERC-721，系列作品（如10000个PFP）用ERC-1155更经济。

#### 1.1.2 链上数据结构

一个NFT包含以下核心数据：

```text
NFT Token
├── tokenId        — 链上唯一标识
├── contractAddress — 所属合约地址
├── ownerAddress   — 当前持有者
├── tokenURI       — 指向元数据的链接
└── metadata       — JSON格式的元数据
    ├── name       — 名称
    ├── description — 描述
    ├── image      — 图片/媒体链接（通常为IPFS）
    ├── attributes — 属性数组（稀有度标签）
    └── animation_url — 动态媒体（可选）
```

元数据通常存储在IPFS（星际文件系统）上而非中心化服务器，因为IPFS的内容寻址机制（CID）保证了：只要内容不变，地址永远不变。如果存储在普通服务器上，服务器关机或域名失效，你的NFT图片就会变成空白。

#### 1.1.3 铸造的经济学原理

铸造（Minting）的本质是在区块链上写入一条交易记录。你需要为这次写入支付Gas费（矿工费），Gas费由两部分组成：

- **Gas Price**：每单位Gas的价格（由网络拥堵程度决定）
- **Gas Limit**：操作需要的最大Gas量（由操作复杂度决定）

以太坊主网在2023年完成Dencun升级后，EIP-4844引入了Blob交易，L2的铸造成本已降至$0.01-0.10区间。但以太坊主网的铸造成本仍然在$2-15之间波动。

**Gas费节省策略：**

- 使用L2网络（Arbitrum、Optimism、Base）：Gas降低90%以上
- 选择周末或UTC凌晨2-5点铸造（网络拥堵最低时段）
- 使用ERC-1155批量铸造（一次交易铸造多个NFT）
- 使用Lazy Minting（OpenSea/Rarible支持，铸造费用由买家承担）
- 设置Gas Price上限，使用"慢速"交易选项

### 1.2 创作准备

#### 1.2.1 数字内容创作工具矩阵

不同创作方向需要不同的工具链，以下是经过社区验证的工具选择：

**图像与绘画：**

| 工具 | 类型 | 价格 | 适用场景 | 学习曲线 |
|------|------|------|----------|----------|
| Photoshop | 位图编辑 | $20.99/月 | 复杂合成、后期处理 | 高 |
| Procreate | 数字绘画 | $12.99（一次性） | iPad绘画、插画 | 中 |
| Illustrator | 矢量设计 | $20.99/月 | PFP项目、Logo | 高 |
| Midjourney | AI生成 | $10-60/月 | 概念探索、素材生成 | 低 |
| DALL-E 3 | AI生成 | ChatGPT Plus内含 | 精确提示词控制 | 低 |
| Stable Diffusion | AI生成（开源） | 免费 | 本地部署、风格微调 | 中高 |
| Clip Studio Paint | 数字绘画 | $49.99/年 | 漫画、插画 | 中 |

**3D建模与动画：**

| 工具 | 类型 | 价格 | 适用场景 |
|------|------|------|----------|
| Blender | 全能3D | 免费 | 建模、动画、渲染 |
| Cinema 4D | 专业3D | $719/年 | 动态图形、广告级渲染 |
| ZBrush | 数字雕刻 | $895/次 | 高精度角色、有机体建模 |
| Houdini | 程序化3D | 免费（学习版） | 粒子特效、生成式3D |

**音乐与音频：**

| 工具 | 类型 | 价格 | 适用场景 |
|------|------|------|----------|
| Ableton Live | DAW | $99-749 | 电子音乐、现场表演 |
| FL Studio | DAW | $99-499 | Beat制作、嘻哈 |
| Audacity | 音频编辑 | 免费 | 简单剪辑、后期处理 |
| Suno AI | AI作曲 | 免费/Pro | 快速生成音乐Demo |

**生成艺术（链上Art）：**

| 工具 | 类型 | 特点 |
|------|------|------|
| p5.js | JavaScript库 | 最流行的生成艺术框架，社区庞大 |
| Processing | Java环境 | p5.js的前身，桌面端更强大 |
| Canvas API | 浏览器原生 | 无依赖，适合链上存储 |
| TouchDesigner | 节点式 | 实时视觉、互动装置 |
| Art Blocks | 平台 | 链上生成艺术的标杆，curated筛选严格 |

#### 1.2.2 创作方向深度分析

选择创作方向不仅看兴趣，还要看市场需求和竞争格局。以下是各方向的详细拆解：

**PFP（Profile Picture）项目：**
- 核心逻辑：10000个算法生成的头像，通过属性稀有度制造稀缺性
- 技术要求：基础层（身体/头/背景）+ 属性层（帽子/眼镜/配饰），PNG分层渲染
- 成功要素：社区运营 > 视觉设计。BAYC的美术水平并不高，但社区文化极强
- 入门建议：先做100-500个的小系列，验证市场反馈后再扩展

**生成艺术：**
- 核心逻辑：用代码生成视觉作品，同一算法+不同随机种子 = 不同输出
- 技术要求：JavaScript/TypeScript + p5.js/Canvas API，理解哈希驱动随机性
- 成功要素：算法美学、可变性范围、系列一致性
- 参考标准：Art Blocks Curated系列要求代码完全链上存储，渲染结果可验证

**1/1艺术（单件原创）：**
- 核心逻辑：传统艺术品的数字化呈现，强调艺术家个人品牌
- 技术要求：与传统艺术创作相同，NFT只是确权和交易的载体
- 成功要素：艺术家个人影响力、叙事深度、策展能力
- 入门平台：Foundation（邀请制，高端定位）、SuperRare（策展严格）

**音乐NFT：**
- 核心逻辑：将音乐作品代币化，持有者获得流媒体分成或独家使用权
- 技术要求：音乐制作能力 + 基本的合约理解
- 平台选择：Sound.xyz（音乐NFT标杆）、Catalog（1/1音乐）、Audius（流媒体+Web3）

### 1.3 NFT铸造全流程

#### 1.3.1 铸造前准备清单

在开始铸造之前，确认以下事项全部就绪：

- [ ] **Web3钱包**：MetaMask（最通用）、Phantom（Solana）、Rainbow（以太坊生态UX最佳）
- [ ] **钱包资金**：至少0.05 ETH（铸造+Gas+应急），从交易所购买后转入
- [ ] **IPFS存储**：Pinata（免费5GB）、NFT.Storage（免费无限，Filecoin驱动）
- [ ] **元数据JSON**：符合OpenSea Metadata Standard的JSON文件
- [ ] **作品文件**：满足平台尺寸/格式要求（通常PNG/JPG/GIF/MP4，<100MB）
- [ ] **版税设置**：确定二级市场版税比例（行业标准5-10%）

#### 1.3.2 元数据标准

元数据是NFT的"身份证"，格式不标准会导致在部分平台无法正确显示。以下是OpenSea兼容的标准格式：

```json
{
  "name": "作品名称 #001",
  "description": "这是一段描述，讲清楚作品的创作背景、灵感来源和艺术理念。",
  "image": "ipfs://QmYourImageCID/001.png",
  "animation_url": "ipfs://QmYourVideoCID/001.mp4",
  "external_url": "https://yourwebsite.com/nft/001",
  "attributes": [
    {
      "trait_type": "Background",
      "value": "Deep Blue"
    },
    {
      "trait_type": "Style",
      "value": "Abstract"
    },
    {
      "trait_type": "Rarity",
      "value": "Legendary"
    },
    {
      "display_type": "number",
      "trait_type": "Generation",
      "value": 1
    },
    {
      "display_type": "date",
      "trait_type": "Created",
      "value": 1704067200
    }
  ],
  "properties": {
    "files": [
      {
        "uri": "ipfs://QmYourImageCID/001.png",
        "type": "image/png"
      }
    ],
    "category": "image"
  }
}
```

**关键注意事项：**
- `image`和`animation_url`必须使用IPFS链接（`ipfs://`前缀），不要用HTTP链接
- `attributes`中的`trait_type`和`value`都是字符串，数字型属性用`display_type: "number"`
- 每个NFT的JSON文件也需要上传到IPFS，然后将JSON的CID作为tokenURI写入合约

#### 1.3.3 IPFS存储实操

IPFS是NFT资产存储的标准方案，以下是使用Pinata上传的完整流程：

**第一步：注册Pinata并获取API Key**

访问 [pinata.cloud](https://pinata.cloud) 注册账号。免费计划包含5GB存储和100GB带宽/月。创建API Key时只勾选需要的权限（`pinFileToIPFS`和`unpin`），不要给管理员权限。

**第二步：上传资产文件**

```bash
# 安装Pinata CLI
npm install -g pinata-upload-cli

# 上传单个文件
pinata upload ./artwork/001.png --pinata-api-key YOUR_KEY --pinata-secret YOUR_SECRET

# 返回结果示例：
# IpfsHash: QmXoYpY1nkzF8K4G5Lm2nR3sT6uV7wX8yZ9aB0cD1eF2gH3
# PinSize: 245760
# Timestamp: 2024-01-01T00:00:00.000Z
```

**第三步：上传元数据JSON**

```bash
# 将所有JSON文件打包上传为目录
pinata upload ./metadata/ --pinata-api-key YOUR_KEY --pinata-secret YOUR_SECRET

# 返回目录的CID，这就是你的baseURI
# 例如：ipfs://QmMetadataDirCID/
# NFT #001的tokenURI就是：ipfs://QmMetadataDirCID/001.json
```

**第四步：验证**

在浏览器中访问 `https://gateway.pinata.cloud/ipfs/QmYourCID` 确认文件可访问。

> **重要提醒：** Pinata的公共网关有时不稳定。生产环境建议使用专用网关（Dedicated Gateway）或自建IPFS节点。另外，将CID同时提交到Filecoin网络可以提供长期存储保障——NFT.Storage会自动处理这一步。

#### 1.3.4 铸造平台详解与操作

**OpenSea（最大综合平台）：**

OpenSea支持两种铸造模式：

1. **Lazy Minting（推荐新手）**：NFT在被购买时才真正上链，创作者零Gas费。缺点是NFT元数据存储在OpenSea服务器上而非IPFS。
2. **标准铸造**：创作者支付Gas费，NFT立即上链，元数据可以指向IPFS。

操作步骤：
1. 访问 opensea.io，连接MetaMask钱包
2. 点击右上角头像 → "Studio" → "Create"
3. 选择集合类型（单个/系列）
4. 上传作品文件，填写名称、描述、外部链接
5. 添加属性（Properties）——这些是稀有度标签
6. 设置版税（Royalties）：选择收款钱包和百分比（1-10%）
7. 选择区块链（Ethereum/Polygon/Klaytn/Arbitrum/Base）
8. 点击"Create"完成铸造

**Manifold（创作者自主铸造）：**

Manifold允许创作者部署自己的智能合约，完全掌控NFT的铸造逻辑。适合有一定技术基础的创作者。

```solidity
// Manifold合约示例：自定义铸造逻辑
// 通过Manifold Studio部署，无需手写合约
// 但理解底层逻辑有助于自定义功能

// 关键参数设置：
// - 名称和符号（如 "MyArt" / "MART"）
// - 最大供应量（如有上限）
// - 铸造价格（可以免费）
// - 铸造时间窗口
// - 白名单（Merkle Proof验证）
```

Manifold的核心优势：
- 合约100%属于你，不依赖任何平台
- 支持Claim Page（铸造页面），可自定义UI
- 支持空投（Airdrop）功能
- 与OpenSea、Blur等市场自动兼容

**其他平台对比：**

| 平台 | 定位 | 费用 | 特色 | 适合人群 |
|------|------|------|------|----------|
| Foundation | 高端艺术 | 5%佣金 | 邀请制，品质把控严格 | 专业艺术家 |
| Zora | 创作者经济 | 0%佣金 | 无平台费，协议层创新 | 技术型创作者 |
| Rarible | 综合平台 | 2.5%佣金 | 支持自定义版税、多链 | 各层级创作者 |
| SuperRare | 精品画廊 | 15%首售/3%二级 | 严格策展，高溢价 | 顶级艺术家 |
| Objkt | Tezos生态 | 2.5%佣金 | Gas极低，艺术社区浓厚 | 新手/独立艺术家 |
| Magic Eden | Solana生态 | 2%佣金 | 交易速度快，PFP项目多 | PFP/游戏项目 |

### 1.4 智能合约设计

#### 1.4.1 为什么需要自定义合约

使用平台提供的铸造合约虽然简单，但存在根本性限制：

- 平台控制合约升级权限，你无法添加新功能
- 版税执行依赖平台配合（链上版税EIP-2981只是接口标准，不是强制执行）
- 无法实现复杂逻辑：动态NFT、可升级元数据、链上随机性

自定义合约给你完全控制权，以下是核心功能模块：

#### 1.4.2 核心合约功能

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract MyNFT is ERC721, Ownable {
    uint256 private _tokenIdCounter;
    uint256 public constant MAX_SUPPLY = 10000;
    uint256 public mintPrice = 0.01 ether;
    string private _baseTokenURI;

    constructor() ERC721("MyNFT", "MNFT") Ownable(msg.sender) {}

    // 公开铸造
    function mint(uint256 quantity) public payable {
        require(quantity > 0 && quantity <= 10, "Invalid quantity");
        require(_tokenIdCounter + quantity <= MAX_SUPPLY, "Sold out");
        require(msg.value >= mintPrice * quantity, "Insufficient payment");

        for (uint256 i = 0; i < quantity; i++) {
            uint256 tokenId = _tokenIdCounter++;
            _safeMint(msg.sender, tokenId);
        }
    }

    // 白名单铸造（Merkle Proof验证）
    function mintWhitelist(
        uint256 quantity,
        bytes32[] calldata proof
    ) public payable {
        bytes32 leaf = keccak256(abi.encodePacked(msg.sender));
        require(_verifyProof(proof, merkleRoot, leaf), "Not whitelisted");
        // ... 铸造逻辑
    }

    // 版税标准（EIP-2981）
    function royaltyInfo(uint256 tokenId, uint256 salePrice)
        public view returns (address receiver, uint256 royaltyAmount)
    {
        return (owner(), (salePrice * 500) / 10000); // 5% 版税
    }

    function _baseURI() internal view override returns (string memory) {
        return _baseTokenURI;
    }
}
```

#### 1.4.3 部署与验证

使用Remix IDE（最简单）或Hardhat（专业开发）部署：

```bash
# Hardhat方式
npm init -y
npm install --save-dev hardhat @openzeppelin/contracts
npx hardhat init  # 选择"Create a JavaScript project"

# 编写合约后编译
npx hardhat compile

# 部署到测试网（Sepolia）
npx hardhat run scripts/deploy.js --network sepolia

# 部署到主网
npx hardhat run scripts/deploy.js --network mainnet

# 在Etherscan上验证合约源码（增加透明度和信任度）
npx hardhat verify --network mainnet DEPLOYED_CONTRACT_ADDRESS
```

### 1.5 NFT定价策略

#### 1.5.1 定价因素分析框架

NFT定价不是拍脑袋，而是一个多因素决策：

**成本基础法：**
- 创作时间 × 时薪（至少按$30-50/小时计算你的技能价值）
- 工具/软件成本分摊
- Gas费成本
- 营销和社区运营成本

**市场比较法：**
- 同类型、同质量作品的近期成交价
- 同层级创作者的定价区间
- 所在平台的平均成交价

**稀缺性定价法：**
- 1/1作品 > 系列中的稀有属性 > 普通属性
- 版数越少价格越高（1/1 > /10 > /100 > /10000）
- 铸造时间窗口限制制造稀缺

#### 1.5.2 定价策略详解

**固定价格（Fixed Price）：**
- 最简单直接，买家看到价格直接购买
- 适合：有稳定受众的创作者、系列作品中的普通款
- 技巧：设定略高于心理底价的价格，留出议价空间

**英式拍卖（English Auction）：**
- 设置起拍价和持续时间（通常24-72小时），价高者得
- 适合：高价值1/1作品、市场热度高的项目
- 技巧：起拍价设为心理预期的30-50%，制造竞争氛围

**荷兰式拍卖（Dutch Auction）：**
- 起始高价，随时间自动降价，直到有人购买或达到底价
- 适合：系列作品首发、测试市场真实估值
- 案例：Art Blocks项目常用此模式。起拍价2ETH，每10分钟降0.1ETH，底价0.3ETH
- 优势：消除Gas War（竞价导致的Gas费飙升），让买家选择自己的"心理价位"

**Bonding Curve定价：**
- 价格随已售数量递增：第1个0.01ETH，第100个0.05ETH，第1000个0.2ETH
- 适合：社区驱动项目、治理代币化NFT
- 实现：通过智能合约自动计算

**免费铸造（Free Mint）+ 铸造后收费：**
- 初始免费铸造吸引用户，后续通过版税、升级、空投变现
- 适合：快速扩大持有者基数、Meme类项目
- 风险：容易被机器人扫货，需要配合白名单或社交验证

#### 1.5.3 版税的现实困境

2023年以来，NFT版税面临严峻挑战：

- Blur、OpenSea等平台纷纷将版税变为可选（买家可以设为0%）
- 链上ERC-2981版税标准只是接口，市场可以不执行
- 部分项目通过Operator Filter Registry强制收取版税，但覆盖范围有限

**应对策略：**
1. 将版税视为"额外收入"而非核心商业模式
2. 通过实体赋能（线下活动、实物周边）创造收费场景
3. 使用Manifold合约，在Claim时直接收费而非依赖二级版税
4. 构建强社区，让持有者自发维护版税文化

### 1.6 常见陷阱与避坑指南

#### 1.6.1 创作阶段

**陷阱1：使用AI生成内容却不声明**
- 风险：社区对AI Art的接受度两极分化，隐瞒会引发信任危机
- 正确做法：明确标注"AI-assisted"或"AI-generated"，并说明AI参与的程度

**陷阱2：素材版权问题**
- 风险：使用未授权的素材（字体、背景、音乐采样）铸造NFT，可能面临法律诉讼
- 正确做法：仅使用自制素材或明确标注CC0/CC-BY许可的资源

**陷阱3：元数据格式错误**
- 风险：JSON格式不兼容导致NFT在部分平台显示为空白
- 正确做法：铸造前在OpenSea Testnet上预览，确认所有字段正确显示

#### 1.6.2 铸造阶段

**陷阱4：Gas费超支**
- 场景：在网络拥堵时铸造，Gas费可能超过作品本身价值
- 预防：使用Etherscan Gas Tracker监控，设置Gas Price上限

**陷阱5：发送到错误网络**
- 场景：将Ethereum主网NFT误发到测试网，资产不可恢复
- 预防：每次铸造前双重确认网络选择，MetaMask会在切换网络时提示

**陷阱6：合约地址钓鱼**
- 场景：点击假铸造链接，签署恶意交易，钱包被清空
- 预防：只通过官方渠道访问铸造页面，使用Revoke.cash定期检查授权

#### 1.6.3 运营阶段

**陷阱7：刷量制造假繁荣**
- 风险：Wash Trading（自己卖给自己）已被链上分析工具识别，会导致平台封禁
- 正确做法：专注真实社区建设，耐心等待有机增长

**陷阱8：承诺过多赋能却无法兑现**
- 风险：持有者期望落空引发抛售，项目信誉崩塌
- 正确做法：只承诺你能100%做到的事情，做到之后再承诺下一件

### 1.7 进阶话题

#### 1.7.1 动态NFT（dNFT）

动态NFT的元数据可以根据外部条件（链上事件、预言机数据、持有者行为）自动变化。

```text
静态NFT：image永远指向同一张图
动态NFT：image根据条件变化
  ├── 时间触发：每年生日自动更新形象
  ├── 事件触发：持有者完成成就后解锁新外观
  ├── 预言机触发：天气NFT随真实天气变化
  └── 交互触发：持有者投票决定下一步演化
```

实现方式：tokenURI指向一个API端点，API根据条件返回不同的元数据JSON。Chainlink VRF可以提供链上可验证的随机性。

#### 1.7.2 链上存储 vs 链下存储

| 维度 | 完全链上 | IPFS+链上指针 | 中心化服务器 |
|------|----------|---------------|--------------|
| 永久性 | 最高（区块链不消失） | 高（需要持续pin） | 低（服务器可能关停） |
| 成本 | 极高（存储成本=Gas） | 中等（IPFS存储费） | 低 |
| 灵活性 | 低（写入后不可改） | 中（可更新指针） | 高 |
| 信任假设 | 无 | 需信任pinning服务 | 需信任平台 |
| 适用场景 | Art Blocks Curated | 大多数NFT项目 | 平台铸造（Lazy Minting） |

#### 1.7.3 多链部署策略

同一个NFT系列部署到多条链上，需要考虑：

- **跨链桥**：使用LayerZero或Wormhole实现NFT跨链转移
- **统一元数据**：所有链使用同一个IPFS CID，确保视觉一致性
- **社区管理**：不同链上的持有者可能形成独立社区，需要统一治理
- **价格差异**：同系列在不同链上的地板价可能差异很大

### 1.8 实操案例：从零铸造一个100件系列

以下是一个完整的小型NFT系列铸造流程：

**第1步：设计系列**
- 主题：极简几何风格，100件，每件独一无二
- 层级：背景（10种）× 形状（8种）× 颜色方案（6种）× 特效（3种）= 1440种组合，随机抽取100个

**第2步：生成作品**
```python
# Python脚本生成100个独特作品
from PIL import Image, ImageDraw
import random
import json

backgrounds = ["#1a1a2e", "#16213e", "#0f3460", "#533483", "#e94560",
               "#2d4059", "#ea5455", "#f07b3f", "#ffd460", "#00b8a9"]
shapes = ["circle", "square", "triangle", "diamond", "hexagon",
          "star", "pentagon", "cross"]
color_schemes = ["warm", "cool", "neon", "pastel", "monochrome", "rainbow"]
effects = ["none", "glow", "shadow", "gradient"]

used_combinations = set()
nfts = []

for i in range(100):
    while True:
        combo = (random.choice(backgrounds),
                 random.choice(shapes),
                 random.choice(color_schemes),
                 random.choice(effects))
        if combo not in used_combinations:
            used_combinations.add(combo)
            break

    bg, shape, scheme, effect = combo
    img = Image.new("RGB", (1000, 1000), bg)
    draw = ImageDraw.Draw(img)
    # ... 绘制逻辑（根据shape和scheme绘制具体图形）

    img.save(f"./artwork/{i:03d}.png")

    # 生成对应元数据
    metadata = {
        "name": f"GeoArt #{i:03d}",
        "description": "极简几何风格生成艺术系列",
        "image": f"ipfs://YOUR_CID/{i:03d}.png",
        "attributes": [
            {"trait_type": "Background", "value": bg},
            {"trait_type": "Shape", "value": shape},
            {"trait_type": "Color Scheme", "value": scheme},
            {"trait_type": "Effect", "value": effect}
        ]
    }
    with open(f"./metadata/{i:03d}.json", "w") as f:
        json.dump(metadata, f, indent=2)

print("100个NFT作品和元数据已生成")
```

**第3步：上传到IPFS**
- 将`artwork/`目录上传到Pinata → 得到资产CID
- 将`metadata/`目录上传到Pinata → 得到元数据CID
- 更新元数据中的image字段为正确的IPFS链接

**第4步：部署合约**
- 在Sepolia测试网部署并测试
- 确认所有NFT可在OpenSea Testnet正确显示
- 部署到主网

**第5步：铸造与销售**
- 先开放白名单铸造（24小时）：0.008 ETH/个
- 再开放公开铸造：0.01 ETH/个
- 设置5%版税
- 铸造完成后在OpenSea上查看系列页面

### 1.9 本节检查清单

铸造完成后，逐项确认：

- [ ] 所有作品已上传到IPFS，CID稳定可访问
- [ ] 元数据JSON格式正确，在多个平台预览无异常
- [ ] 合约已部署并验证源码（Etherscan）
- [ ] 版税设置正确，收款钱包无误
- [ ] 测试网铸造测试通过（至少铸造1-3个测试NFT）
- [ ] Gas费预算充足，铸造时间窗口合理
- [ ] 社交媒体公告已发布，铸造链接已验证
- [ ] 白名单地址已整理完毕（如适用）
- [ ] 应急方案准备：如铸造出问题，如何通知社区并处理

***

