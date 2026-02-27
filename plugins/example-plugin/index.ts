/**
 * OpenClaw Plugin 示例模板
 * 
 * Plugin 可以注册:
 * - Gateway RPC 方法
 * - Agent 工具
 * - CLI 命令
 * - 后台服务
 * - 自动回复命令
 * - Channel 插件
 * - Provider 认证流程
 */

export default function register(api: any) {
  const logger = api.logger;

  // 1. 注册 Gateway RPC 方法
  api.registerGatewayMethod("example.ping", ({ respond }: any) => {
    respond(true, { 
      ok: true, 
      message: "pong from example plugin",
      timestamp: new Date().toISOString(),
    });
  });

  // 2. 注册自动回复命令（不经过 AI 处理）
  api.registerCommand({
    name: "example",
    description: "Example plugin status check",
    handler: (ctx: any) => ({
      text: `Example plugin is running! Channel: ${ctx.channel}`,
    }),
  });

  // 3. 注册后台服务
  api.registerService({
    id: "example-service",
    start: () => {
      logger.info("[example-plugin] Service started");
    },
    stop: () => {
      logger.info("[example-plugin] Service stopped");
    },
  });

  // 4. 注册 CLI 命令
  api.registerCli(
    ({ program }: any) => {
      program
        .command("example-status")
        .description("Show example plugin status")
        .action(() => {
          console.log("Example plugin is loaded and ready!");
        });
    },
    { commands: ["example-status"] },
  );

  logger.info("[example-plugin] Plugin registered successfully");
}
