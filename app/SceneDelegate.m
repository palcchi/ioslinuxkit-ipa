//
//  SceneDelegate.m
//  V-MINE
//
//  Native iOS/iPadOS shell for the Bedrock Dedicated Server runtime.
//

#import "SceneDelegate.h"
#import "AboutViewController.h"

TerminalViewController *currentTerminalViewController = NULL;

static UIColor *VMineYellow(void) {
    return [UIColor colorWithRed:1.0 green:0.78 blue:0.0 alpha:1.0];
}

static UIColor *VMineBackground(void) {
    return [UIColor colorWithWhite:0.035 alpha:1.0];
}

static UIColor *VMineCard(void) {
    return [UIColor colorWithWhite:0.095 alpha:1.0];
}

static UIColor *VMineSecondary(void) {
    return [UIColor colorWithWhite:0.62 alpha:1.0];
}

static UIButton *VMineButton(NSString *title, NSString *symbol, BOOL primary) {
    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
    button.translatesAutoresizingMaskIntoConstraints = NO;
    button.layer.cornerRadius = 13.0;
    button.titleLabel.font = [UIFont systemFontOfSize:16 weight:UIFontWeightSemibold];
    [button setTitle:title forState:UIControlStateNormal];
    if (@available(iOS 13.0, *)) {
        [button setImage:[UIImage systemImageNamed:symbol] forState:UIControlStateNormal];
        button.imageEdgeInsets = UIEdgeInsetsMake(0, -5, 0, 5);
    }
    if (primary) {
        button.backgroundColor = VMineYellow();
        [button setTitleColor:UIColor.blackColor forState:UIControlStateNormal];
        button.tintColor = UIColor.blackColor;
    } else {
        button.backgroundColor = [UIColor colorWithWhite:0.16 alpha:1.0];
        [button setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
        button.tintColor = UIColor.whiteColor;
    }
    [NSLayoutConstraint activateConstraints:@[[button.heightAnchor constraintEqualToConstant:50]]];
    return button;
}

@interface VMineState : NSObject
@property (nonatomic) BOOL running;
@property (nonatomic, copy) NSString *statusText;
@property (nonatomic, copy) NSString *installedVersion;
@property (nonatomic, strong) NSMutableArray<NSString *> *consoleLines;
+ (instancetype)shared;
- (void)appendLog:(NSString *)line;
@end

static NSString *const VMineStateDidChangeNotification = @"VMineStateDidChangeNotification";

@implementation VMineState
+ (instancetype)shared {
    static VMineState *state;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        state = [VMineState new];
        state.running = NO;
        state.statusText = @"Offline";
        state.installedVersion = [[NSUserDefaults standardUserDefaults] stringForKey:@"VMineInstalledBDSVersion"] ?: @"Not installed";
        state.consoleLines = [NSMutableArray arrayWithObjects:
                              @"V-MINE runtime ready.",
                              @"Install the official Bedrock server from Updates before starting.", nil];
    });
    return state;
}
- (void)appendLog:(NSString *)line {
    if (line.length == 0) return;
    [self.consoleLines addObject:line];
    if (self.consoleLines.count > 1000) {
        [self.consoleLines removeObjectsInRange:NSMakeRange(0, self.consoleLines.count - 1000)];
    }
    [[NSNotificationCenter defaultCenter] postNotificationName:VMineStateDidChangeNotification object:self];
}
@end

@interface VMineBaseViewController : UIViewController
- (UIView *)card;
- (UILabel *)label:(NSString *)text size:(CGFloat)size weight:(UIFontWeight)weight color:(UIColor *)color;
@end

@implementation VMineBaseViewController
- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = VMineBackground();
    self.navigationController.navigationBar.prefersLargeTitles = YES;
    self.navigationController.navigationBar.barStyle = UIBarStyleBlack;
    self.navigationController.navigationBar.tintColor = VMineYellow();
    self.navigationController.navigationBar.largeTitleTextAttributes = @{NSForegroundColorAttributeName: UIColor.whiteColor};
    self.navigationController.navigationBar.titleTextAttributes = @{NSForegroundColorAttributeName: UIColor.whiteColor};
}
- (UIView *)card {
    UIView *view = [UIView new];
    view.translatesAutoresizingMaskIntoConstraints = NO;
    view.backgroundColor = VMineCard();
    view.layer.cornerRadius = 18;
    view.layer.cornerCurve = kCACornerCurveContinuous;
    return view;
}
- (UILabel *)label:(NSString *)text size:(CGFloat)size weight:(UIFontWeight)weight color:(UIColor *)color {
    UILabel *label = [UILabel new];
    label.translatesAutoresizingMaskIntoConstraints = NO;
    label.text = text;
    label.font = [UIFont systemFontOfSize:size weight:weight];
    label.textColor = color;
    label.numberOfLines = 0;
    return label;
}
@end

@interface VMineDashboardViewController : VMineBaseViewController
@property UILabel *statusValue;
@property UILabel *versionValue;
@property UIButton *startButton;
@property UIButton *stopButton;
@end

@implementation VMineDashboardViewController
- (void)viewDidLoad {
    [super viewDidLoad];
    self.title = @"Dashboard";

    UIScrollView *scroll = [UIScrollView new];
    scroll.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:scroll];
    UIView *content = [UIView new];
    content.translatesAutoresizingMaskIntoConstraints = NO;
    [scroll addSubview:content];

    UIView *hero = [self card];
    [content addSubview:hero];
    UILabel *serverName = [self label:@"My Bedrock Server" size:21 weight:UIFontWeightBold color:UIColor.whiteColor];
    [hero addSubview:serverName];
    UILabel *statusCaption = [self label:@"STATUS" size:11 weight:UIFontWeightSemibold color:VMineSecondary()];
    [hero addSubview:statusCaption];
    self.statusValue = [self label:@"Offline" size:15 weight:UIFontWeightSemibold color:VMineYellow()];
    [hero addSubview:self.statusValue];
    UILabel *versionCaption = [self label:@"BEDROCK VERSION" size:11 weight:UIFontWeightSemibold color:VMineSecondary()];
    [hero addSubview:versionCaption];
    self.versionValue = [self label:@"Not installed" size:15 weight:UIFontWeightMedium color:UIColor.whiteColor];
    [hero addSubview:self.versionValue];

    UIView *network = [self card];
    [content addSubview:network];
    UILabel *networkTitle = [self label:@"Local Server" size:17 weight:UIFontWeightSemibold color:UIColor.whiteColor];
    [network addSubview:networkTitle];
    UILabel *address = [self label:@"Address\nThis iPad / iPhone\n\nPort\n19132 UDP" size:14 weight:UIFontWeightRegular color:VMineSecondary()];
    [network addSubview:address];

    self.startButton = VMineButton(@"Start Server", @"play.fill", YES);
    self.stopButton = VMineButton(@"Stop Server", @"stop.fill", NO);
    [content addSubview:self.startButton];
    [content addSubview:self.stopButton];
    [self.startButton addTarget:self action:@selector(startTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.stopButton addTarget:self action:@selector(stopTapped) forControlEvents:UIControlEventTouchUpInside];

    UIView *info = [self card];
    [content addSubview:info];
    UILabel *infoTitle = [self label:@"V-MINE" size:17 weight:UIFontWeightSemibold color:UIColor.whiteColor];
    UILabel *infoText = [self label:@"Official Bedrock Dedicated Server runtime. Worlds and server data stay separate from engine updates." size:14 weight:UIFontWeightRegular color:VMineSecondary()];
    [info addSubview:infoTitle];
    [info addSubview:infoText];

    UILayoutGuide *frame = scroll.frameLayoutGuide;
    UILayoutGuide *layout = scroll.contentLayoutGuide;
    [NSLayoutConstraint activateConstraints:@[
        [scroll.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor],
        [scroll.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor],
        [scroll.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor],
        [scroll.bottomAnchor constraintEqualToAnchor:self.view.bottomAnchor],
        [content.topAnchor constraintEqualToAnchor:layout.topAnchor],
        [content.bottomAnchor constraintEqualToAnchor:layout.bottomAnchor],
        [content.leadingAnchor constraintEqualToAnchor:layout.leadingAnchor],
        [content.trailingAnchor constraintEqualToAnchor:layout.trailingAnchor],
        [content.widthAnchor constraintEqualToAnchor:frame.widthAnchor],

        [hero.topAnchor constraintEqualToAnchor:content.topAnchor constant:18],
        [hero.leadingAnchor constraintEqualToAnchor:content.leadingAnchor constant:18],
        [hero.trailingAnchor constraintEqualToAnchor:content.trailingAnchor constant:-18],
        [serverName.topAnchor constraintEqualToAnchor:hero.topAnchor constant:20],
        [serverName.leadingAnchor constraintEqualToAnchor:hero.leadingAnchor constant:20],
        [serverName.trailingAnchor constraintEqualToAnchor:hero.trailingAnchor constant:-20],
        [statusCaption.topAnchor constraintEqualToAnchor:serverName.bottomAnchor constant:22],
        [statusCaption.leadingAnchor constraintEqualToAnchor:serverName.leadingAnchor],
        [self.statusValue.topAnchor constraintEqualToAnchor:statusCaption.bottomAnchor constant:4],
        [self.statusValue.leadingAnchor constraintEqualToAnchor:serverName.leadingAnchor],
        [versionCaption.topAnchor constraintEqualToAnchor:self.statusValue.bottomAnchor constant:18],
        [versionCaption.leadingAnchor constraintEqualToAnchor:serverName.leadingAnchor],
        [self.versionValue.topAnchor constraintEqualToAnchor:versionCaption.bottomAnchor constant:4],
        [self.versionValue.leadingAnchor constraintEqualToAnchor:serverName.leadingAnchor],
        [self.versionValue.bottomAnchor constraintEqualToAnchor:hero.bottomAnchor constant:-20],

        [network.topAnchor constraintEqualToAnchor:hero.bottomAnchor constant:14],
        [network.leadingAnchor constraintEqualToAnchor:hero.leadingAnchor],
        [network.trailingAnchor constraintEqualToAnchor:hero.trailingAnchor],
        [networkTitle.topAnchor constraintEqualToAnchor:network.topAnchor constant:18],
        [networkTitle.leadingAnchor constraintEqualToAnchor:network.leadingAnchor constant:20],
        [address.topAnchor constraintEqualToAnchor:networkTitle.bottomAnchor constant:12],
        [address.leadingAnchor constraintEqualToAnchor:networkTitle.leadingAnchor],
        [address.trailingAnchor constraintEqualToAnchor:network.trailingAnchor constant:-20],
        [address.bottomAnchor constraintEqualToAnchor:network.bottomAnchor constant:-18],

        [self.startButton.topAnchor constraintEqualToAnchor:network.bottomAnchor constant:16],
        [self.startButton.leadingAnchor constraintEqualToAnchor:hero.leadingAnchor],
        [self.startButton.trailingAnchor constraintEqualToAnchor:hero.trailingAnchor],
        [self.stopButton.topAnchor constraintEqualToAnchor:self.startButton.bottomAnchor constant:10],
        [self.stopButton.leadingAnchor constraintEqualToAnchor:hero.leadingAnchor],
        [self.stopButton.trailingAnchor constraintEqualToAnchor:hero.trailingAnchor],

        [info.topAnchor constraintEqualToAnchor:self.stopButton.bottomAnchor constant:16],
        [info.leadingAnchor constraintEqualToAnchor:hero.leadingAnchor],
        [info.trailingAnchor constraintEqualToAnchor:hero.trailingAnchor],
        [infoTitle.topAnchor constraintEqualToAnchor:info.topAnchor constant:18],
        [infoTitle.leadingAnchor constraintEqualToAnchor:info.leadingAnchor constant:20],
        [infoText.topAnchor constraintEqualToAnchor:infoTitle.bottomAnchor constant:8],
        [infoText.leadingAnchor constraintEqualToAnchor:infoTitle.leadingAnchor],
        [infoText.trailingAnchor constraintEqualToAnchor:info.trailingAnchor constant:-20],
        [infoText.bottomAnchor constraintEqualToAnchor:info.bottomAnchor constant:-18],
        [info.bottomAnchor constraintEqualToAnchor:content.bottomAnchor constant:-28]
    ]];

    [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(refresh) name:VMineStateDidChangeNotification object:nil];
    [self refresh];
}
- (void)refresh {
    VMineState *state = VMineState.shared;
    self.statusValue.text = state.statusText;
    self.statusValue.textColor = state.running ? [UIColor colorWithRed:0.35 green:0.9 blue:0.4 alpha:1] : VMineYellow();
    self.versionValue.text = state.installedVersion;
    self.stopButton.enabled = state.running;
    self.stopButton.alpha = state.running ? 1.0 : 0.5;
}
- (void)startTapped {
    VMineState *state = VMineState.shared;
    if ([state.installedVersion isEqualToString:@"Not installed"]) {
        [state appendLog:@"Start blocked: install the official Bedrock server from Updates first."];
        UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Bedrock Server Not Installed" message:@"Open Updates and install the official Mojang Bedrock Dedicated Server first." preferredStyle:UIAlertControllerStyleAlert];
        [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
        [self presentViewController:alert animated:YES completion:nil];
        return;
    }
    [state appendLog:@"Start requested. V-MINE runtime bridge is preparing the server process."];
}
- (void)stopTapped {
    [VMineState.shared appendLog:@"Stop requested."];
}
@end

@interface VMineConsoleViewController : VMineBaseViewController <UITextFieldDelegate>
@property UITextView *textView;
@property UITextField *commandField;
@end

@implementation VMineConsoleViewController
- (void)viewDidLoad {
    [super viewDidLoad];
    self.title = @"Console";
    self.textView = [UITextView new];
    self.textView.translatesAutoresizingMaskIntoConstraints = NO;
    self.textView.backgroundColor = VMineCard();
    self.textView.textColor = [UIColor colorWithWhite:0.88 alpha:1];
    self.textView.font = [UIFont monospacedSystemFontOfSize:12.5 weight:UIFontWeightRegular];
    self.textView.editable = NO;
    self.textView.layer.cornerRadius = 16;
    self.textView.textContainerInset = UIEdgeInsetsMake(14, 14, 14, 14);
    [self.view addSubview:self.textView];

    self.commandField = [UITextField new];
    self.commandField.translatesAutoresizingMaskIntoConstraints = NO;
    self.commandField.backgroundColor = [UIColor colorWithWhite:0.14 alpha:1];
    self.commandField.textColor = UIColor.whiteColor;
    self.commandField.tintColor = VMineYellow();
    self.commandField.attributedPlaceholder = [[NSAttributedString alloc] initWithString:@"Type a server command" attributes:@{NSForegroundColorAttributeName: VMineSecondary()}];
    self.commandField.font = [UIFont monospacedSystemFontOfSize:14 weight:UIFontWeightRegular];
    self.commandField.layer.cornerRadius = 13;
    self.commandField.leftView = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 14, 1)];
    self.commandField.leftViewMode = UITextFieldViewModeAlways;
    self.commandField.returnKeyType = UIReturnKeySend;
    self.commandField.delegate = self;
    [self.view addSubview:self.commandField];

    [NSLayoutConstraint activateConstraints:@[
        [self.textView.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor constant:12],
        [self.textView.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor constant:16],
        [self.textView.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor constant:-16],
        [self.commandField.topAnchor constraintEqualToAnchor:self.textView.bottomAnchor constant:10],
        [self.commandField.leadingAnchor constraintEqualToAnchor:self.textView.leadingAnchor],
        [self.commandField.trailingAnchor constraintEqualToAnchor:self.textView.trailingAnchor],
        [self.commandField.heightAnchor constraintEqualToConstant:48],
        [self.commandField.bottomAnchor constraintEqualToAnchor:self.view.keyboardLayoutGuide.topAnchor constant:-12]
    ]];
    [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(refresh) name:VMineStateDidChangeNotification object:nil];
    [self refresh];
}
- (void)refresh {
    self.textView.text = [VMineState.shared.consoleLines componentsJoinedByString:@"\n"];
    if (self.textView.text.length > 0) {
        [self.textView scrollRangeToVisible:NSMakeRange(self.textView.text.length - 1, 1)];
    }
}
- (BOOL)textFieldShouldReturn:(UITextField *)textField {
    NSString *command = [textField.text stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
    if (command.length == 0) return NO;
    [VMineState.shared appendLog:[NSString stringWithFormat:@"> %@", command]];
    textField.text = @"";
    return NO;
}
@end

@interface VMineListViewController : VMineBaseViewController <UITableViewDataSource, UITableViewDelegate>
@property UITableView *tableView;
@property NSArray<NSDictionary *> *items;
@property NSString *emptyText;
@end

@implementation VMineListViewController
- (void)viewDidLoad {
    [super viewDidLoad];
    self.tableView = [[UITableView alloc] initWithFrame:CGRectZero style:UITableViewStyleInsetGrouped];
    self.tableView.translatesAutoresizingMaskIntoConstraints = NO;
    self.tableView.backgroundColor = VMineBackground();
    self.tableView.separatorColor = [UIColor colorWithWhite:0.2 alpha:1];
    self.tableView.dataSource = self;
    self.tableView.delegate = self;
    [self.view addSubview:self.tableView];
    [NSLayoutConstraint activateConstraints:@[
        [self.tableView.topAnchor constraintEqualToAnchor:self.view.topAnchor],
        [self.tableView.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor],
        [self.tableView.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor],
        [self.tableView.bottomAnchor constraintEqualToAnchor:self.view.bottomAnchor]
    ]];
}
- (NSInteger)tableView:(UITableView *)tableView numberOfRowsInSection:(NSInteger)section { return MAX((NSInteger)self.items.count, 1); }
- (UITableViewCell *)tableView:(UITableView *)tableView cellForRowAtIndexPath:(NSIndexPath *)indexPath {
    UITableViewCell *cell = [tableView dequeueReusableCellWithIdentifier:@"vmine"] ?: [[UITableViewCell alloc] initWithStyle:UITableViewCellStyleSubtitle reuseIdentifier:@"vmine"];
    cell.backgroundColor = VMineCard();
    cell.textLabel.textColor = UIColor.whiteColor;
    cell.detailTextLabel.textColor = VMineSecondary();
    cell.imageView.tintColor = VMineYellow();
    if (self.items.count == 0) {
        cell.textLabel.text = self.emptyText ?: @"Nothing here yet";
        cell.detailTextLabel.text = nil;
        cell.selectionStyle = UITableViewCellSelectionStyleNone;
        if (@available(iOS 13.0, *)) cell.imageView.image = [UIImage systemImageNamed:@"tray"];
    } else {
        NSDictionary *item = self.items[indexPath.row];
        cell.textLabel.text = item[@"title"];
        cell.detailTextLabel.text = item[@"detail"];
        cell.accessoryType = UITableViewCellAccessoryDisclosureIndicator;
        if (@available(iOS 13.0, *)) cell.imageView.image = [UIImage systemImageNamed:item[@"symbol"] ?: @"square"];
    }
    return cell;
}
@end

@interface VMineWorldsViewController : VMineListViewController @end
@implementation VMineWorldsViewController
- (void)viewDidLoad {
    self.items = @[];
    self.emptyText = @"No worlds imported yet";
    [super viewDidLoad];
    self.title = @"Worlds";
    self.navigationItem.rightBarButtonItem = [[UIBarButtonItem alloc] initWithBarButtonSystemItem:UIBarButtonSystemItemAdd target:self action:@selector(importWorld)];
}
- (void)importWorld {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Import World" message:@"World import will use the iOS Files picker and store worlds separately from the updateable BDS engine." preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
    [self presentViewController:alert animated:YES completion:nil];
}
@end

@interface VMinePlayersViewController : VMineListViewController @end
@implementation VMinePlayersViewController
- (void)viewDidLoad {
    self.items = @[];
    self.emptyText = @"No players online";
    [super viewDidLoad];
    self.title = @"Players";
}
@end

@interface VMineUpdatesViewController : VMineBaseViewController
@property UILabel *installedLabel;
@end
@implementation VMineUpdatesViewController
- (void)viewDidLoad {
    [super viewDidLoad];
    self.title = @"Updates";
    UIView *card = [self card];
    [self.view addSubview:card];
    UILabel *title = [self label:@"Official Bedrock Server" size:20 weight:UIFontWeightBold color:UIColor.whiteColor];
    UILabel *source = [self label:@"Source: Minecraft / Mojang" size:13 weight:UIFontWeightMedium color:VMineSecondary()];
    self.installedLabel = [self label:@"Installed: Not installed" size:15 weight:UIFontWeightMedium color:UIColor.whiteColor];
    UIButton *check = VMineButton(@"Check for Updates", @"arrow.down.circle.fill", YES);
    [check addTarget:self action:@selector(checkUpdates) forControlEvents:UIControlEventTouchUpInside];
    [card addSubview:title]; [card addSubview:source]; [card addSubview:self.installedLabel]; [card addSubview:check];
    [NSLayoutConstraint activateConstraints:@[
        [card.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor constant:20],
        [card.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor constant:18],
        [card.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor constant:-18],
        [title.topAnchor constraintEqualToAnchor:card.topAnchor constant:20],
        [title.leadingAnchor constraintEqualToAnchor:card.leadingAnchor constant:20],
        [title.trailingAnchor constraintEqualToAnchor:card.trailingAnchor constant:-20],
        [source.topAnchor constraintEqualToAnchor:title.bottomAnchor constant:6],
        [source.leadingAnchor constraintEqualToAnchor:title.leadingAnchor],
        [self.installedLabel.topAnchor constraintEqualToAnchor:source.bottomAnchor constant:22],
        [self.installedLabel.leadingAnchor constraintEqualToAnchor:title.leadingAnchor],
        [check.topAnchor constraintEqualToAnchor:self.installedLabel.bottomAnchor constant:22],
        [check.leadingAnchor constraintEqualToAnchor:title.leadingAnchor],
        [check.trailingAnchor constraintEqualToAnchor:title.trailingAnchor],
        [check.bottomAnchor constraintEqualToAnchor:card.bottomAnchor constant:-20]
    ]];
    [self refresh];
}
- (void)refresh { self.installedLabel.text = [NSString stringWithFormat:@"Installed: %@", VMineState.shared.installedVersion]; }
- (void)checkUpdates {
    [VMineState.shared appendLog:@"Update check requested from official Minecraft source."];
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Update Manager" message:@"The native updater shell is ready. Network download and atomic engine replacement are being wired to the BDS runtime layer." preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
    [self presentViewController:alert animated:YES completion:nil];
}
@end

@interface VMineSettingsViewController : VMineListViewController @end
@implementation VMineSettingsViewController
- (void)viewDidLoad {
    self.items = @[
        @{@"title": @"Server Name", @"detail": @"My Bedrock Server", @"symbol": @"server.rack"},
        @{@"title": @"Game Mode", @"detail": @"Survival", @"symbol": @"gamecontroller"},
        @{@"title": @"Difficulty", @"detail": @"Normal", @"symbol": @"dial.medium"},
        @{@"title": @"Max Players", @"detail": @"20", @"symbol": @"person.2"},
        @{@"title": @"Port", @"detail": @"19132", @"symbol": @"network"},
        @{@"title": @"Updates", @"detail": @"Official Mojang BDS", @"symbol": @"arrow.down.circle"}
    ];
    [super viewDidLoad];
    self.title = @"Settings";
}
- (void)tableView:(UITableView *)tableView didSelectRowAtIndexPath:(NSIndexPath *)indexPath {
    [tableView deselectRowAtIndexPath:indexPath animated:YES];
    if (indexPath.row == 5) {
        [self.navigationController pushViewController:[VMineUpdatesViewController new] animated:YES];
    }
}
@end

@interface VMineSidebarViewController : UITableViewController
@property NSArray<NSDictionary *> *entries;
@property (nonatomic, copy) void (^selectionHandler)(NSInteger index);
@end
@implementation VMineSidebarViewController
- (void)viewDidLoad {
    [super viewDidLoad];
    self.title = @"V-MINE";
    self.tableView.backgroundColor = [UIColor colorWithWhite:0.055 alpha:1];
    self.tableView.separatorStyle = UITableViewCellSeparatorStyleNone;
    self.entries = @[
        @{@"title": @"Dashboard", @"symbol": @"rectangle.grid.2x2.fill"},
        @{@"title": @"Console", @"symbol": @"terminal.fill"},
        @{@"title": @"Worlds", @"symbol": @"shippingbox.fill"},
        @{@"title": @"Players", @"symbol": @"person.2.fill"},
        @{@"title": @"Settings", @"symbol": @"gearshape.fill"},
        @{@"title": @"Updates", @"symbol": @"arrow.down.circle.fill"}
    ];
}
- (NSInteger)tableView:(UITableView *)tableView numberOfRowsInSection:(NSInteger)section { return self.entries.count; }
- (UITableViewCell *)tableView:(UITableView *)tableView cellForRowAtIndexPath:(NSIndexPath *)indexPath {
    UITableViewCell *cell = [tableView dequeueReusableCellWithIdentifier:@"sidebar"] ?: [[UITableViewCell alloc] initWithStyle:UITableViewCellStyleDefault reuseIdentifier:@"sidebar"];
    NSDictionary *entry = self.entries[indexPath.row];
    cell.textLabel.text = entry[@"title"];
    cell.textLabel.textColor = UIColor.whiteColor;
    cell.backgroundColor = UIColor.clearColor;
    cell.tintColor = VMineYellow();
    if (@available(iOS 13.0, *)) cell.imageView.image = [UIImage systemImageNamed:entry[@"symbol"]];
    return cell;
}
- (void)tableView:(UITableView *)tableView didSelectRowAtIndexPath:(NSIndexPath *)indexPath {
    if (self.selectionHandler) self.selectionHandler(indexPath.row);
}
@end

@interface SceneDelegate ()
@property NSString *terminalUUID;
@property (nonatomic, strong) TerminalViewController *engineTerminalViewController;
@end

static NSString *const TerminalUUID = @"TerminalUUID";

@implementation SceneDelegate

- (UIViewController *)viewControllerForIndex:(NSInteger)index {
    switch (index) {
        case 1: return [VMineConsoleViewController new];
        case 2: return [VMineWorldsViewController new];
        case 3: return [VMinePlayersViewController new];
        case 4: return [VMineSettingsViewController new];
        case 5: return [VMineUpdatesViewController new];
        default: return [VMineDashboardViewController new];
    }
}

- (UINavigationController *)navigationForIndex:(NSInteger)index {
    UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:[self viewControllerForIndex:index]];
    nav.navigationBar.tintColor = VMineYellow();
    nav.navigationBar.barStyle = UIBarStyleBlack;
    return nav;
}

- (UIViewController *)buildPhoneRoot {
    UITabBarController *tabs = [UITabBarController new];
    tabs.tabBar.barStyle = UIBarStyleBlack;
    tabs.tabBar.tintColor = VMineYellow();
    tabs.tabBar.unselectedItemTintColor = [UIColor colorWithWhite:0.55 alpha:1.0];
    tabs.tabBar.backgroundColor = [UIColor colorWithWhite:0.055 alpha:1.0];

    NSArray *titles = @[@"Home", @"Console", @"Worlds", @"Players", @"Settings"];
    NSArray *symbols = @[@"rectangle.grid.2x2.fill", @"terminal.fill", @"shippingbox.fill", @"person.2.fill", @"gearshape.fill"];
    NSMutableArray *controllers = [NSMutableArray array];
    for (NSInteger i = 0; i < titles.count; i++) {
        UINavigationController *nav = [self navigationForIndex:i];
        nav.tabBarItem.title = titles[i];
        if (@available(iOS 13.0, *)) nav.tabBarItem.image = [UIImage systemImageNamed:symbols[i]];
        [controllers addObject:nav];
    }
    tabs.viewControllers = controllers;
    return tabs;
}

- (UIViewController *)buildPadRoot API_AVAILABLE(ios(14.0)) {
    UISplitViewController *split = [[UISplitViewController alloc] initWithStyle:UISplitViewControllerStyleDoubleColumn];
    split.preferredDisplayMode = UISplitViewControllerDisplayModeOneBesideSecondary;
    split.preferredSplitBehavior = UISplitViewControllerSplitBehaviorTile;
    split.minimumPrimaryColumnWidth = 230;
    split.maximumPrimaryColumnWidth = 300;

    VMineSidebarViewController *sidebar = [VMineSidebarViewController new];
    UINavigationController *sideNav = [[UINavigationController alloc] initWithRootViewController:sidebar];
    UINavigationController *detail = [self navigationForIndex:0];
    [split setViewController:sideNav forColumn:UISplitViewControllerColumnPrimary];
    [split setViewController:detail forColumn:UISplitViewControllerColumnSecondary];

    __weak typeof(self) weakSelf = self;
    __weak UISplitViewController *weakSplit = split;
    sidebar.selectionHandler = ^(NSInteger index) {
        __strong typeof(weakSelf) self = weakSelf;
        if (!self) return;
        UINavigationController *next = [self navigationForIndex:index];
        [weakSplit setViewController:next forColumn:UISplitViewControllerColumnSecondary];
        [weakSplit showColumn:UISplitViewControllerColumnSecondary];
    };
    [sidebar.tableView selectRowAtIndexPath:[NSIndexPath indexPathForRow:0 inSection:0] animated:NO scrollPosition:UITableViewScrollPositionNone];
    return split;
}

- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session options:(UISceneConnectionOptions *)connectionOptions {
    if ([NSUserDefaults.standardUserDefaults boolForKey:@"recovery"]) {
        UINavigationController *vc = [[UIStoryboard storyboardWithName:@"About" bundle:nil] instantiateInitialViewController];
        AboutViewController *avc = (AboutViewController *)vc.topViewController;
        avc.recoveryMode = YES;
        self.window.rootViewController = vc;
        return;
    }

    // The Terminal storyboard still creates the legacy controller because it
    // owns the pseudo-terminal plumbing. Keep it alive as a hidden engine
    // controller while presenting a fully native V-MINE UI to the user.
    if ([self.window.rootViewController isKindOfClass:TerminalViewController.class]) {
        self.engineTerminalViewController = (TerminalViewController *)self.window.rootViewController;
        self.engineTerminalViewController.sceneSession = session;
    }

    UIViewController *root;
    if (UIDevice.currentDevice.userInterfaceIdiom == UIUserInterfaceIdiomPad) {
        if (@available(iOS 14.0, *)) root = [self buildPadRoot];
        else root = [self buildPhoneRoot];
    } else {
        root = [self buildPhoneRoot];
    }
    self.window.rootViewController = root;
    self.window.backgroundColor = VMineBackground();
    [self.window makeKeyAndVisible];
}

- (NSUserActivity *)stateRestorationActivityForScene:(UIScene *)scene {
    NSUserActivity *activity = [[NSUserActivity alloc] initWithActivityType:@"app.vmine.scene"];
    if (self.engineTerminalViewController.sessionTerminalUUID != nil) {
        self.terminalUUID = self.engineTerminalViewController.sessionTerminalUUID.UUIDString;
        if (self.terminalUUID != nil) [activity addUserInfoEntriesFromDictionary:@{TerminalUUID: self.terminalUUID}];
    }
    return activity;
}

- (void)sceneDidBecomeActive:(UIScene *)scene {
    currentTerminalViewController = self.engineTerminalViewController;
}

- (void)sceneWillResignActive:(UIScene *)scene {
    if (currentTerminalViewController == self.engineTerminalViewController) currentTerminalViewController = NULL;
}

@end
